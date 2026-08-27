"""Run 引擎：状态机 + Keyset 批次复制 + 批次级交错验证，见 04 §2/§3/§5/§7/§8/§9。

V1 不具备 Purge 能力（Copy is automatic. Destruction is explicit.）。
"""
from __future__ import annotations

import time
from datetime import date

from PySide6.QtCore import QThread, Signal

from ..domain.run import ArchiveBatch, BatchStatus, RunStatus
from ..domain.task import ArchiveTask, VerifyMode
from ..oracle import copy as oc
from ..oracle import ddl as od
from ..oracle import metadata as md
from ..oracle.copy import LOB_TYPES
from ..repositories.run_repository import RunRepository
from ..utils.ids import new_batch_id
from ..utils.time import now_iso

# 04 §8：可重试 / 不可重试分类
RETRYABLE = ("ORA-03113", "ORA-03114", "ORA-03135", "ORA-12170", "ORA-12541", "ORA-12543")
BACKOFFS = (1, 5, 15)


def is_retryable(exc: Exception) -> bool:
    return any(code in str(exc) for code in RETRYABLE)


def with_retry(fn, log=None):
    """单批次 3 次重试，指数退避 1s/5s/15s（04 §8）。"""
    attempts = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if is_retryable(exc) and attempts < len(BACKOFFS):
                if log:
                    log(f"可重试错误，{BACKOFFS[attempts]}s 后重试：{exc}")
                time.sleep(BACKOFFS[attempts])
                attempts += 1
                continue
            raise


class RunWorker(QThread):
    """后台执行单个 Run；GUI 通过 changed/done 信号刷新。"""

    changed = Signal(str)          # run_id
    done = Signal(str, str)        # run_id, final status

    def __init__(self, repo: RunRepository, open_conn, run_id: str,
                 resume: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.open_conn = open_conn
        self.run_id = run_id
        self.resume = resume
        self._pause = False

    def request_pause(self) -> None:
        """04 §7：不杀线程，当前批次完整执行结束后落 PAUSED。"""
        self._pause = True

    # ---- 日志快捷 ----
    def _log(self, stage: str, message: str, level: str = "INFO",
             batch_id: str | None = None) -> None:
        self.repo.append_log(self.run_id, batch_id, level, stage, message)

    def run(self) -> None:
        repo = self.repo
        run = repo.get_run(self.run_id)
        if run is None:
            return
        task = ArchiveTask(**run.task_snapshot)
        if self.resume:
            repo.update_run(self.run_id, status=RunStatus.RUNNING)
        self.changed.emit(self.run_id)

        src = tgt = None
        try:
            src = self.open_conn(task.source_connection_id)
            tgt = self.open_conn(task.target_connection_id)
            src_cols = self._prepare(task, src, tgt)
            self._loop(run, task, src, tgt, src_cols)
        except Exception as exc:
            repo.update_run(
                self.run_id, status=RunStatus.FAILED,
                error_message=str(exc), end_time=now_iso(),
            )
            self._log("RUN", f"Run 失败：{exc}", level="ERROR")
        finally:
            for c in (src, tgt):
                if c is not None:
                    try:
                        c.close()
                    except Exception:
                        pass
        final = repo.get_run(self.run_id)
        self.changed.emit(self.run_id)
        self.done.emit(self.run_id, final.status.value if final else "UNKNOWN")

    # ---- 准备：目标表创建 + 结构检查（04 §1、05 §11）----
    def _prepare(self, task: ArchiveTask, src, tgt) -> list[md.ColumnMeta]:
        repo = self.repo
        src_cols = md.get_columns(src, task.source_schema, task.source_table)
        if not src_cols:
            raise ValueError(f"源表不存在或无列：{task.source_schema}.{task.source_table}")

        if task.create_target_if_missing:
            pk = md.get_primary_key(src, task.source_schema, task.source_table)
            uks = md.get_unique_keys(src, task.source_schema, task.source_table)
            if od.ensure_target_table(tgt, task.target_schema, task.target_table,
                                      src_cols, pk, uks):
                tgt.commit()
                self._log("PREPARE", f"目标表已创建：{task.target_schema}.{task.target_table}")

        if not od.table_exists(tgt, task.target_schema, task.target_table):
            raise ValueError(
                f"目标表不存在：{task.target_schema}.{task.target_table}"
                "（可在任务中开启“如果不存在则创建”，见 05 §11）"
            )
        mism = md.compare_columns(src_cols, md.get_columns(tgt, task.target_schema, task.target_table))
        if mism:
            raise ValueError("源/目标结构不一致，禁止执行：" + "；".join(mism[:5]))
        return src_cols

    # ---- 主循环 ----
    def _loop(self, run, task, src, tgt, src_cols) -> None:
        repo = self.repo
        col_names = [c.name for c in src_cols]
        col_types = {c.name: c.data_type for c in src_cols}
        keys = task.key_columns
        key_idx = [col_names.index(k) for k in keys]

        cutoff = date.fromisoformat(run.cutoff_value) if run.cutoff_value and task.archive_column else None
        cond_params: dict = {"cutoff": cutoff} if cutoff is not None else {}

        last_keys: list | None = None
        batch_no = 0
        transferred = run.transferred_rows
        verified = run.verified_rows
        success = run.success_batches
        failed = run.failed_batches
        stop_reason = ""

        # Resume 起点（04 §5）：COPIED/VERIFYING 重新验证；中断的 COPYING 补拷；
        # last_keys 只从数据已落目标库的批次推进，避免跳过从未复制的行。
        if self.resume:
            batches = repo.list_batches(self.run_id)
            n_redo = sum(1 for b in batches
                         if b.status in (BatchStatus.COPIED, BatchStatus.VERIFYING))
            n_cut = sum(1 for b in batches if b.status is BatchStatus.COPYING)
            self._log("RESUME", f"Resume 开始：{n_redo} 个批次需重新验证，"
                                f"{n_cut} 个中断批次需补拷")
            for b in batches:
                snap = b.selection_snapshot or {}
                landed = False
                if b.status is BatchStatus.COPYING:
                    landed = self._recopy_interrupted(b, task, src, tgt,
                                                      col_names, col_types, keys)
                    if not landed:
                        failed += 1
                elif b.status in (BatchStatus.COPIED, BatchStatus.VERIFYING):
                    view = _BatchView(
                        prev=snap.get("prev_keys"), last=snap.get("last_keys"),
                        rows=None, selected_rows=b.selected_rows,
                        batch_no=b.batch_no, batch_id=b.batch_id,
                    )
                    if self._verify_batch(view, task, src, tgt, col_names, col_types, keys,
                                          run.archive_condition or None, cond_params):
                        repo.update_batch(b.batch_id, status=BatchStatus.VERIFIED,
                                          verified_rows=b.selected_rows,
                                          verify_end_time=now_iso(), end_time=now_iso())
                        success += 1
                        verified += b.selected_rows
                        landed = True
                        self._log("RESUME", f"批次 {b.batch_no} 重新验证通过",
                                  batch_id=b.batch_id)
                    else:
                        repo.update_batch(b.batch_id, status=BatchStatus.FAILED,
                                          error_message="Resume 重新验证失败",
                                          end_time=now_iso())
                        failed += 1
                        self._log("RESUME", f"批次 {b.batch_no} 重新验证失败",
                                  "ERROR", b.batch_id)
                elif b.status is BatchStatus.VERIFIED:
                    landed = True
                if landed and snap.get("last_keys") is not None:
                    last_keys = snap["last_keys"]
                    batch_no = b.batch_no
            repo.update_run(self.run_id, transferred_rows=transferred,
                            verified_rows=verified, success_batches=success,
                            failed_batches=failed)
            self._log("RESUME", f"续跑起点：batch_no={batch_no}")

        # 含 LOB 列的表自动缩小批次：单批数据驻留内存，5000 × MB 级 CLOB
        # 会达数 GB 且耗时极长（用户体感卡死）；200 行兼顾吞吐与响应。
        eff_batch = task.batch_size
        if any(t in LOB_TYPES for t in col_types.values()) and eff_batch > 200:
            eff_batch = 200
            self._log("RUN", f"检测到 LOB 列，批次大小自动调整为 {eff_batch}"
                             f"（任务配置 {task.batch_size}）")

        while True:
            if self._pause:
                repo.update_run(self.run_id, status=RunStatus.PAUSED)
                self._log("RUN", "用户暂停，当前批次已完整执行结束")
                return

            sql = oc.build_select_sql(
                task.source_schema, task.source_table, col_names,
                run.archive_condition or None,
                keys, last_keys,
            )
            params = dict(cond_params)
            params["batch_size"] = eff_batch
            if last_keys is not None:
                for i, v in enumerate(last_keys):
                    params[f"lk{i}"] = v
            self._log("COPY", f"批次 {batch_no + 1} 开始选取数据…")
            rows = oc.select_batch(src, sql, params, eff_batch)
            if not rows:
                break

            batch_no += 1
            last = [rows[-1][i] for i in key_idx]
            prev = last_keys
            batch_id = new_batch_id(self.run_id, batch_no)
            repo.create_batch(ArchiveBatch(
                batch_id=batch_id, run_id=self.run_id, batch_no=batch_no,
                status=BatchStatus.PENDING, start_time=now_iso(),
            ))
            repo.update_batch(
                batch_id,
                selection_snapshot={"prev_keys": prev, "last_keys": last},
                selected_rows=len(rows), status=BatchStatus.COPYING,
            )
            self._log("COPY", f"批次 {batch_no} 已选取 {len(rows)} 行，开始写入目标库…",
                      batch_id=batch_id)

            # Copy：Target executemany + commit（MERGE 幂等）；失败绝不触发 Purge（04 §2）
            try:
                def do_copy():
                    n = oc.insert_batch(tgt, task.target_schema, task.target_table,
                                        col_names, rows, col_types, keys)
                    tgt.commit()
                    return n
                n = with_retry(do_copy, log=lambda m: self._log("COPY", m, "WARN", batch_id))
            except Exception as exc:
                failed += 1
                repo.update_batch(batch_id, status=BatchStatus.FAILED,
                                  error_message=str(exc), end_time=now_iso())
                repo.update_run(self.run_id, failed_batches=failed,
                                total_batches=batch_no)
                self._log("COPY", f"批次 {batch_no} 复制失败：{exc}", "ERROR", batch_id)
                last_keys = last  # FAILED 不阻塞后续批次（04 §8）
                continue

            transferred += n
            repo.update_batch(batch_id, status=BatchStatus.COPIED,
                              transferred_rows=n, copy_end_time=now_iso())

            # 复制完成后再检查一次暂停：CLOB 等大批次复制耗时长，
            # 批间等待不可接受；批次已落 COPIED，Resume 会重新验证（04 §5）。
            if self._pause:
                repo.update_run(self.run_id, status=RunStatus.PAUSED,
                                transferred_rows=transferred, verified_rows=verified,
                                success_batches=success, failed_batches=failed,
                                total_batches=batch_no)
                self._log("RUN", "用户暂停：批次已复制完成，验证留待 Resume")
                return

            # Verify：批次级交错，单批 COPIED 后立即验证（04 §3）
            repo.update_batch(batch_id, status=BatchStatus.VERIFYING)
            ok = self._verify_batch(
                _BatchView(prev=prev, last=last, rows=rows, selected_rows=len(rows),
                           batch_no=batch_no, batch_id=batch_id),
                task, src, tgt, col_names, col_types, keys,
                run.archive_condition or None, cond_params,
            )
            if ok:
                success += 1
                verified += len(rows)
                repo.update_batch(batch_id, status=BatchStatus.VERIFIED,
                                  verified_rows=len(rows), verify_end_time=now_iso(),
                                  end_time=now_iso())
                self._log("VERIFY", f"批次 {batch_no} 验证通过（{task.verify_mode.value}）",
                          batch_id=batch_id)
            else:
                failed += 1
                repo.update_batch(batch_id, status=BatchStatus.FAILED,
                                  error_message="验证失败", end_time=now_iso())
                self._log("VERIFY", f"批次 {batch_no} 验证失败", "ERROR", batch_id)

            repo.update_run(
                self.run_id, transferred_rows=transferred, verified_rows=verified,
                success_batches=success, failed_batches=failed, total_batches=batch_no,
            )
            self.changed.emit(self.run_id)
            last_keys = last

            if task.max_rows_per_run and transferred >= task.max_rows_per_run:
                stop_reason = "max_rows"
                self._log("RUN", f"已达 max_rows_per_run={task.max_rows_per_run}，停止新批次（03 §7）")
                break

        repo.update_run(self.run_id, copy_end_time=now_iso(), verify_end_time=now_iso())
        if failed > 0:
            final = RunStatus.FAILED
            repo.update_run(self.run_id, status=final, end_time=now_iso(),
                            error_message=f"{failed} 个批次失败")
        elif stop_reason == "max_rows":
            final = RunStatus.COPY_COMPLETED
            repo.update_run(self.run_id, status=final)
        else:
            if task.allow_purge:
                final = RunStatus.VERIFIED  # 等待人工 Purge 后再 COMPLETED
            else:
                # 任务禁止 Purge：校验通过即终态，不阻塞后续运行（04 §9）
                final = RunStatus.COMPLETED
            extra = {"end_time": now_iso()} if final is RunStatus.COMPLETED else {}
            repo.update_run(self.run_id, status=final, **extra)
        self._log("RUN", f"Run 结束：{final.value}")

    # ---- 中断批次补拷 ----
    def _recopy_interrupted(self, b, task, src, tgt, col_names, col_types, keys) -> bool:
        """补拷中断的 COPYING 批次（进程退出后未提交事务已自动回滚，目标无脏数据）。

        返回是否已落目标库（供 last_keys 推进判断）。
        """
        repo = self.repo
        snap = b.selection_snapshot or {}
        prev, last = snap.get("prev_keys"), snap.get("last_keys")
        if last is None:
            repo.update_batch(b.batch_id, status=BatchStatus.FAILED,
                              error_message="中断且无区间快照，无法补拷", end_time=now_iso())
            self._log("RESUME", f"批次 {b.batch_no} 中断且无区间快照，标记失败",
                      "ERROR", b.batch_id)
            return False
        try:
            cond, params = oc._range_cond(keys, prev, last)
            cols = ", ".join(f"t.{oc._q(c)}" for c in col_names)
            order = ", ".join(f"t.{oc._q(k)}" for k in keys)
            sql = (f"SELECT {cols} FROM {oc._q(task.source_schema)}"
                   f".{oc._q(task.source_table)} t WHERE {cond} ORDER BY {order}")
            rows = oc.select_batch(src, sql, params,
                                   max(b.selected_rows or 1, task.batch_size))
            n = oc.insert_batch(tgt, task.target_schema, task.target_table,
                                col_names, rows, col_types, keys)
            tgt.commit()
            repo.update_batch(b.batch_id, status=BatchStatus.COPIED,
                              transferred_rows=n, copy_end_time=now_iso())
            self._log("RESUME", f"批次 {b.batch_no} 中断补拷完成（{n} 行）",
                      batch_id=b.batch_id)
            return True
        except Exception as exc:
            repo.update_batch(b.batch_id, status=BatchStatus.FAILED,
                              error_message=str(exc), end_time=now_iso())
            self._log("RESUME", f"批次 {b.batch_no} 补拷失败：{exc}", "ERROR", b.batch_id)
            return False

    # ---- 验证 ----
    def _verify_batch(self, b, task, src, tgt, col_names, col_types, keys,
                      cond: str | None = None, cond_params: dict | None = None) -> bool:
        """COUNT / PK / HASH 三种模式（04 §3、09 Verify Mode）。异常视为失败。

        源端叠加归档条件，排除区间内不满足条件的交错行（本就不该归档）。
        """
        try:
            prev, last = b.prev, b.last
            if task.verify_mode is VerifyMode.COUNT:
                return (
                    oc.count_range(tgt, task.target_schema, task.target_table, keys, prev, last)
                    == b.selected_rows
                    and oc.count_range(src, task.source_schema, task.source_table, keys,
                                       prev, last, cond, cond_params)
                    == b.selected_rows
                )
            if task.verify_mode is VerifyMode.PK:
                kidx = [col_names.index(k) for k in keys]
                want = {tuple(r[i] for i in kidx) for r in b.rows} \
                    if getattr(b, "rows", None) else None
                tgt_keys = oc.fetch_keys_range(tgt, task.target_schema, task.target_table, keys, prev, last)
                if len(tgt_keys) != b.selected_rows:
                    return False
                if want is not None:
                    # 键值类型可能不同（如 Decimal vs int），统一转 str 比较
                    return {tuple(str(x) for x in k) for k in tgt_keys} == \
                           {tuple(str(x) for x in k) for k in want}
                return True
            # HASH
            return oc.hash_sum_range(
                tgt, task.target_schema, task.target_table, col_names, col_types, keys, prev, last
            ) == oc.hash_sum_range(
                src, task.source_schema, task.source_table, col_names, col_types, keys,
                prev, last, cond, cond_params
            )
        except Exception as exc:
            self._log("VERIFY", f"验证异常：{exc}", "ERROR", getattr(b, "batch_id", None))
            return False


class _BatchView:
    """主循环内传递批次上下文的轻量视图。"""

    def __init__(self, prev, last, rows, selected_rows, batch_no, batch_id) -> None:
        self.prev = prev
        self.last = last
        self.rows = rows
        self.selected_rows = selected_rows
        self.batch_no = batch_no
        self.batch_id = batch_id
