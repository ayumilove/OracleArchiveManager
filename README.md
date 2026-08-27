# Oracle Archive Manager 开发文档包

## 1. 项目定位

**Oracle Archive Manager** 是一个面向 Oracle 数据库的大表历史数据归档工具。

第一版目标：

- Python C/S 桌面程序；
- PySide6 GUI；
- Oracle 11g 生产库 → 独立 Oracle 归档库；
- 生产表与归档表保持同名、同结构；
- 支持按日期字段/自定义条件归档；
- 分批复制、验证、人工清理生产库；
- 支持暂停、恢复、失败续跑；
- 默认低侵入，不修改业务表、不创建触发器、不依赖 DB Link；
- 控制数据保存在本地 SQLite；
- 默认“Copy + Verify”，生产库 Purge 必须显式确认。

## 2. 文档目录

设计与开发文档统一存放在 [`docs/`](docs/)：

| 文件 | 内容 |
|---|---|
| [`docs/01_PRODUCT_REQUIREMENTS.md`](docs/01_PRODUCT_REQUIREMENTS.md) | 产品需求与范围 |
| [`docs/02_ARCHITECTURE_DESIGN.md`](docs/02_ARCHITECTURE_DESIGN.md) | 总体架构设计 |
| [`docs/03_DATA_MODEL.md`](docs/03_DATA_MODEL.md) | SQLite 控制库数据模型 |
| [`docs/04_ARCHIVE_WORKFLOW.md`](docs/04_ARCHIVE_WORKFLOW.md) | 归档、验证、清理状态机 |
| [`docs/05_ORACLE_STRATEGY.md`](docs/05_ORACLE_STRATEGY.md) | Oracle 11g 数据访问与性能策略 |
| [`docs/06_GUI_DESIGN.md`](docs/06_GUI_DESIGN.md) | PySide6 GUI 页面与交互设计 |
| [`docs/07_SECURITY_SAFETY.md`](docs/07_SECURITY_SAFETY.md) | 数据安全、权限与防误操作 |
| [`docs/08_DEVELOPMENT_PLAN.md`](docs/08_DEVELOPMENT_PLAN.md) | 分阶段开发计划 |
| [`docs/09_TODO.md`](docs/09_TODO.md) | 可执行 Todo List |
| [`docs/10_TEST_PLAN.md`](docs/10_TEST_PLAN.md) | 测试与验收方案 |
| [`docs/11_PROJECT_STRUCTURE.md`](docs/11_PROJECT_STRUCTURE.md) | Python 工程目录和模块职责 |
| [`docs/12_RELEASE_DEPLOYMENT.md`](docs/12_RELEASE_DEPLOYMENT.md) | 打包、部署、升级与配置 |
| [`docs/13_OPEN_SOURCE_PLAN.md`](docs/13_OPEN_SOURCE_PLAN.md) | 后续开源策略建议 |
| [`docs/14_DECISIONS.md`](docs/14_DECISIONS.md) | 当前已经确定的技术决策 |

## 3. V1 核心原则

> Copy is automatic. Destruction is explicit.

1. 复制可以自动执行。
2. 删除生产数据必须经过验证。
3. 删除必须由用户显式触发。
4. 任一批次验证失败，生产库该批次不得删除。
5. 程序崩溃后必须能判断数据处于 COPY / VERIFIED / PURGED 哪个阶段。
6. 所有归档边界在 RUN 创建时冻结，恢复任务不能重新计算。
7. 归档工具不修改业务表结构。
8. 生产库默认使用只读账号；Purge 可以单独使用具备 DELETE 权限的账号。

## 4. 推荐技术栈

- Python 3.12+
- PySide6
- python-oracledb（安装名 `oracledb`）
- SQLite
- SQLAlchemy（仅控制库可选）
- loguru / 标准 logging
- pydantic
- Nuitka（发布）
- pytest

## 5. 第一版不做

- MySQL / PostgreSQL / SQL Server 支持
- Oracle CDC
- 实时同步
- 自动创建生产库对象
- DB Link
- Data Pump 自动编排
- 全自动无人审批 Purge
- Web/B/S
- 多租户
- 分布式 Worker
