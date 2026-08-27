# 产品需求文档（PRD）

## 1. 背景

长期运行的 Oracle 11g 生产系统中，大表持续累积历史数据，导致：

- 表和索引体积持续增长；
- 查询和维护成本上升；
- 备份时间、存储空间增加；
- 业务又不敢直接删除历史数据；
- 历史数据仍需保留并可查询。

目标是将满足归档条件的数据从生产 Oracle 迁移到独立归档 Oracle，在确认数据完整后安全清理生产库。

## 2. 目标用户

- DBA
- ERP/MES/WMS 系统开发与运维人员
- 制造业内部 IT
- 使用 Oracle 11g/12c/19c 的传统业务系统维护人员

## 3. 核心场景

### 场景 A：分析

用户选择生产库表，指定日期字段及保留月份，系统计算：

- 总行数；
- 待归档行数；
- 最早/最新日期；
- 表大小；
- 索引大小；
- 预计归档范围。

### 场景 B：归档

系统以固定 Batch Size 分批：

1. 从生产库读取；
2. 写入归档库同名表；
3. 提交归档库；
4. 校验该批数据；
5. 标记 VERIFIED。

### 场景 C：清理生产库

用户在 Copy + Verify 完成后主动执行 Purge。

系统：

1. 展示待删除数量和条件；
2. 二次确认；
3. 按已验证批次删除；
4. 分批提交；
5. 写入审计日志。

### 场景 D：恢复

程序异常关闭、网络断开、Oracle 异常后：

- 可识别未完成 RUN；
- 可识别未完成 Batch；
- 不重复删除；
- 已写目标但未清源的数据可重新验证；
- 已完成批次不重复处理。

## 4. V1 功能范围

### 4.1 连接管理

- 新建生产库连接；
- 新建归档库连接；
- 测试连接；
- 获取 Oracle 版本；
- 获取 Schema；
- 密码本地安全保存或不保存。

### 4.2 归档任务

- 任务名称；
- Source Connection；
- Source Schema；
- Source Table；
- Target Connection；
- Target Schema；
- Target Table；
- 目标表创建策略（如果不存在则创建，默认关闭，仅归档库）；
- Archive Column（可选；留空 = 按附加 WHERE 或全表归档）；
- Keep Months；
- 可选附加 WHERE；
- Key Columns；
- Batch Size；
- Verify Mode；
- Enabled。

### 4.3 执行

- Analyze / Dry Run；
- Start；
- Pause（当前批次完成后暂停）；
- Resume；
- Stop（安全停止）；
- Copy Only；
- Copy + Verify；
- Manual Purge。

### 4.4 校验

V1 支持：

- 行数校验；
- 主键/唯一键存在性校验；
- 可选关键字段 Hash 校验。

### 4.5 日志

- Run 日志；
- Batch 日志；
- 错误详情；
- Oracle Error；
- 导出日志。

## 5. 非功能要求

- 默认不影响生产业务；
- 不逐行 INSERT；
- 支持 fetchmany + executemany；
- UI 不阻塞；
- 可在 Windows 内网离线运行；
- 不需要生产 Oracle 安装 Agent；
- 不需要 DB Link；
- 不需要修改业务表；
- 所有高风险操作可审计。

## 6. 验收标准

V1 验收必须通过：

- 100 万行测试表完整归档；
- 人为中断至少 5 个阶段后均可恢复；
- 任意校验失败时源库不得删除；
- 重复点击 Resume 不产生重复数据；
- 生产库 DELETE 仅作用于已验证数据；
- 源/目标结构不一致时禁止执行；
- Oracle 11g 测试通过。
