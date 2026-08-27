# 归档流程与状态机

## 1. Analyze

```text
选择 Task
  ↓
测试 Source / Target
  ↓
检查源表结构
  ↓
检查目标表结构
  ↓
检查主键/唯一键
  ↓
计算 cutoff
  ↓
冻结 archive condition
  ↓
COUNT 待归档数据
  ↓
生成 Dry Run 报告
```

## 2. Copy

每批：

```text
CREATE BATCH
    ↓
SELECT 固定批次数据
    ↓
COPYING
    ↓
TARGET executemany
    ↓
TARGET COMMIT
    ↓
COPIED
```

注意：

- Source 不提交；
- Target 成功后才能进入 Verify；
- COPY 失败绝不触发 Purge。

## 3. Verify

```text
COPIED
  ↓
验证目标库该批 Key
  ↓
COUNT
  ↓
可选 HASH
  ↓
VERIFIED
```

如果失败：

```text
FAILED
源数据保持不动
```

验证时机：

- Verify 以批次为单位，与 Copy 交错执行：单批 COPIED 后即可开始该批 Verify，不必等待全部批次 Copy 完成；
- Run 状态 VERIFIED 仅在该 Run 内所有批次均达到 VERIFIED 后出现；
- 任一批次验证失败，该批次不得进入 Purge，Run 不得进入 VERIFIED。

## 4. Purge

仅 VERIFIED Batch 可进入 Purge。

```text
用户点击 Purge
   ↓
Purge Preview
   ↓
二次确认
   ↓
使用已验证 Batch selection
   ↓
Source DELETE
   ↓
Source COMMIT
   ↓
COMPLETED
```

## 5. Resume

启动程序时扫描：

- RUNNING；
- PAUSING；
- COPYING；
- COPIED；
- VERIFYING；
- PURGING。

恢复策略：

| 状态 | 恢复动作 |
|---|---|
| COPYING | 查询 Target 判断是否已写入，必要时重新 Copy |
| COPIED | 重新 Verify |
| VERIFYING | 重新 Verify |
| VERIFIED | 等待人工 Purge 或继续下一 Batch |
| PURGING | 查询 Source/Target，根据实际状态恢复 |
| COMPLETED | 不操作 |

## 6. 固定归档边界

cutoff 计算规则：`(Run 创建日期 - KEEP_MONTHS 个月) 所在月的月初一日`（月初对齐，不随日号变化）。

例如：

```text
KEEP_MONTHS = 24
RUN 创建时间 = 2026-08-27
CUTOFF = 2024-08-01
```

Run 恢复时仍使用：

```text
2024-08-01
```

禁止重新计算“当前时间 - 24个月”。

归档条件三种模式：

1. **日期字段**：`archive_column < :cutoff`，可叠加附加 WHERE；
2. **仅附加 WHERE**：无日期字段时，条件 = `(extra_where)`，不涉及 cutoff；
3. **全表归档**：两者皆空，无 WHERE，复制源表全部数据（Purge 将清空源表，需人工复核）。

## 7. Pause

Pause 不杀线程。

```text
用户点击暂停
   ↓
RUN = PAUSING
   ↓
当前 Batch 完整执行结束
   ↓
RUN = PAUSED
```

## 8. 重试策略

错误分两类：

| 类别 | 典型 Oracle 错误 | 处理 |
|---|---|---|
| 可重试 | ORA-03113 / ORA-03114（连接中断）、Listener 不可用、临时超时 | 自动重试 |
| 不可重试 | 唯一约束冲突、结构不一致、权限不足、表空间满 | 立即 FAILED |

重试规则：

- 单批次默认重试 3 次，指数退避（1s / 5s / 15s），重试次数可配置；
- Copy 重试前先查询 Target 判断已写入范围，决定重做或续跑（与 §5 Resume 策略一致）；
- 重试耗尽后 Batch = FAILED，源数据保持不动；
- FAILED Batch 不阻塞其他批次继续执行；Run 结束时若存在 FAILED Batch，Run = FAILED，等待人工处理或 Resume。

## 9. 并发控制

- 同一 Task 同一时刻只允许一个活动 Run（状态非 COMPLETED / FAILED / CANCELED）；
- Task 已存在活动 Run 时，创建新 Run 必须被拒绝并提示；
- Pause / Resume / Safe Stop 仅作用于当前活动 Run。
