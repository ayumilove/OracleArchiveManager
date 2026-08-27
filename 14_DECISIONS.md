# 当前技术决策记录

## ADR-001：采用 C/S

决定：

```text
Python + PySide6
```

原因：

- 内网数据库工具；
- 用户少；
- 无需部署 Web；
- 客户端可同时访问双 Oracle；
- 易于打包独立 EXE。

## ADR-002：归档库表名与生产库相同

例如：

```text
PROD.APP.ORDERS_HIST
→
ARCHIVE.APP.ORDERS_HIST
```

原因：

- 归档数据库本身已经表达 Archive 语义；
- 结构易保持 1:1；
- 简化映射和历史查询。

## ADR-003：控制数据放 SQLite

不把 `ARCHIVE_TASK/RUN/BATCH/LOG` 作为生产库控制中心。

原因：

- 降低生产库侵入；
- 管理多个 Oracle 更自然；
- 生产库不可用时仍可读取任务状态。

## ADR-004：生产库默认不新增对象

V1 不要求：

- Trigger；
- Scheduler；
- DB Link；
- Archive Flag；
- Stored Procedure。

## ADR-005：Batch 模式

默认：

```text
5000 rows / batch
```

允许配置。

## ADR-006：Purge 人工触发

V1：

```text
Copy
→ Verify
→ Manual Purge
```

不做无人确认自动清理。

## ADR-007：GUI 与 Core 分离

未来可在不重写 Core 的情况下增加：

- FastAPI；
- Web；
- CLI。

## ADR-008：未开源阶段授权独立于归档核心

License 不参与数据事务。

授权失效只能：

- 禁止新任务；
- 禁止 Copy/Purge；
- 允许只读历史。

不得破坏业务数据。

## ADR-009：允许创建目标表

决定：

```text
目标（归档）库支持“如果不存在则创建”，默认关闭
```

原因：

- 降低归档库初始部署成本；
- 目标库非生产库，风险可控；
- “不自动创建生产库对象”仍然成立，生产库保持零 DDL。

约束：

- 用户显式开启；
- 仅生成表结构与主键 / 唯一键；
- 创建后必须通过结构检查。
