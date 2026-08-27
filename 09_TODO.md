# TODO

## P0 - 必须完成

### 工程

- [x] 初始化 Git 仓库
- [x] 建立 Python 虚拟环境
- [x] 建立 `src/` 包结构
- [x] 引入 PySide6
- [x] 引入 python-oracledb（安装名 oracledb）
- [x] 引入 pytest
- [x] 建立 SQLite migration
- [x] 建立统一 logging

### Connection

- [x] ARCHIVE_CONNECTION 模型
- [x] 新建连接
- [x] 编辑连接
- [x] 删除连接
- [x] 测试 Oracle 连接
- [x] 获取 Oracle version
- [x] 凭据安全保存

### Metadata

- [x] 获取 Schema
- [x] 获取 Table
- [x] 获取 Columns
- [x] 获取 PK
- [x] 获取 Unique Key
- [x] 获取表统计信息
- [x] 比较 Source/Target schema

### Task

- [x] ARCHIVE_TASK 模型
- [x] 新建 Task
- [x] 编辑 Task
- [x] 禁用 Task
- [x] 自动建议目标同名表
- [x] Archive Column 选择
- [x] 无日期字段归档（仅 WHERE / 全表）
- [x] Keep Months
- [x] Extra Where
- [x] Key Columns
- [x] 复合主键支持
- [x] Batch Size
- [x] Verify Mode

### Analyze

- [x] Cutoff 计算
- [x] Freeze condition
- [x] Count eligible rows
- [x] Dry Run
- [x] 风险检查
- [x] Analyze Report

### Run

- [x] ARCHIVE_RUN
- [x] ARCHIVE_BATCH
- [x] ARCHIVE_LOG
- [x] Run ID 生成
- [x] Batch ID 生成
- [x] Task Snapshot
- [x] 状态机

### Copy

- [x] Batch selection
- [x] fetchmany
- [x] executemany
- [x] Target commit
- [x] Copy retry
- [x] Pause
- [x] Resume
- [x] Safe Stop

### Verify

- [x] Count Verify
- [x] PK Verify
- [x] Verify failure blocking
- [x] Optional Hash Verify

### Purge

- [x] Purge Preview
- [x] 人工输入表名确认
- [ ] Purger credential
- [x] Delete only VERIFIED batch
- [x] Batch commit
- [x] Purge retry
- [x] Purge audit
- [x] Purge resume

### GUI

- [x] MainWindow（标题栏 / 状态栏 / 左侧导航）
- [x] 首页仪表盘（连接概览 + 任务列表 + 任务详情）
- [x] 当前运行面板（五步进度 + 实时统计 + 运行日志 + 批次列表）
- [x] 任务管理页（含运行历史 / 调度设置预留 / 高级设置 Tabs）
- [x] 运行管理页
- [x] 连接管理页
- [x] 日志查看页
- [x] 系统设置页
- [x] Purge Preview Dialog
- [x] Error Detail Dialog

### 稳定性（对应 Phase 5）

- [x] CLOB 测试（真实 CLOB 大表；Thick 模式 LOB locator 不能跨连接绑定，取批改为内联读取）
- [x] BLOB 测试（真实 BLOB 表 9252 行 VERIFIED；PIC 列全为 NULL，大体积二进制待真实数据再验；结构校验放宽“源非空→目标可空”）

## P1 - 建议完成

- [x] 启动 Splash（品牌标识 + 启动进度文案，主窗体就绪后自动关闭）
- [x] 导出 Analyze Report（任务页“分析报告”卡片右上角“导出报告”，Markdown）
- [x] 导出 Run Report（运行页“导出 Run 报告”，含批次明细/日志/维护建议）
- [x] DBMS_STATS 建议（报告内附 GATHER_TABLE_STATS 可执行 SQL）
- [x] 表空间回收建议（SHRINK SPACE CASCADE 主方案 + MOVE/REBUILD 备选）
- [x] 日志压缩（loguru 轮转文件自动 gzip）
- [x] 自动清理旧 SQLite Log（db_log_retention_days 默认 90 天，启动时清理，设置页可调）

## P2 - 后续版本

- [x] 调度任务（任务级每日定点自动运行，应用内 QTimer 调度，不补跑/跳过记日志）
- [ ] Email
- [ ] 企业微信通知
- [ ] Data Pump Engine
- [ ] DB Link Engine
- [ ] Web API
- [ ] B/S
- [ ] 多 Oracle 版本认证测试
- [ ] 开源版构建
