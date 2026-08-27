# 开发计划

## Phase 0：项目骨架

目标：程序可启动、SQLite 初始化、Oracle 可连接。

交付：

- PySide6 MainWindow；
- 项目目录；
- SQLite migration；
- Connection CRUD；
- Oracle connection test；
- 日志框架。

## Phase 1：Analyze

目标：完成只读分析。

交付：

- Schema/Table 获取；
- Column metadata；
- PK/Unique Key 获取；
- Source/Target schema comparison；
- Cutoff 计算；
- Eligible Count；
- Dry Run UI。

此阶段不具备 DELETE 能力。

## Phase 2：Copy Engine

目标：安全分批复制。

交付：

- Run 创建；
- Batch 创建；
- fetchmany；
- executemany；
- Target commit；
- Pause；
- Safe Stop；
- 执行进度；
- 运行日志。

## Phase 3：Verify Engine

目标：Copy 结果可验证。

交付：

- COUNT Verify；
- PK Verify；
- Verify 失败阻断；
- VERIFIED 状态；
- Resume。

## Phase 4：Purge

目标：安全清理生产库。

交付：

- Purge Preview；
- 表名二次确认；
- Purge 权限独立；
- Batch DELETE；
- Commit；
- 审计；
- Purge Resume。

## Phase 5：稳定性

目标：生产试用。

交付：

- 网络中断测试；
- Oracle 重启测试；
- 客户端强杀测试；
- 重复执行测试；
- LOB 测试；
- 性能测试；
- Bug Fix。

## Phase 6：发布

交付：

- Nuitka Build；
- 安装包；
- 配置迁移；
- 版本信息；
- 用户手册；
- ChangeLog。

## 建议开发顺序

```text
Connection
   ↓
Metadata
   ↓
Analyze
   ↓
Copy
   ↓
Verify
   ↓
Resume
   ↓
Purge
   ↓
UI polish
```

不要先开发漂亮 GUI 再补核心安全逻辑。
