# 测试计划

## 1. 测试环境

至少准备：

- Oracle 11g Source；
- Oracle 11g Archive；
- Windows Client；
- 1 万 / 10 万 / 100 万 / 500 万测试数据集。

## 2. 功能测试

### Connection

- 正确账号；
- 错误密码；
- 服务不可达；
- Listener Down；
- Session 被杀。

### Schema

- 完全一致；
- 缺字段；
- 类型不同；
- 长度不同；
- 精度不同；
- 无 PK；
- 联合 PK。

### Copy

- 正常；
- 中途网络断；
- Target tablespace 满；
- Unique Constraint；
- 客户端强杀；
- Oracle Source 重启；
- Oracle Target 重启。

### Verify

- 少一条；
- 多一条；
- PK 不一致；
- Hash 不一致。

### Purge

- 无 DELETE 权限；
- Verify 未完成；
- 删除一半断网；
- 删除后程序强杀；
- 重复 Resume。

## 3. 崩溃注入测试

必须在以下位置 kill 程序：

1. Batch 创建后；
2. Source 读取后；
3. Target insert 未 commit；
4. Target commit 后；
5. Verify 开始前；
6. Verify 完成后；
7. Source delete 未 commit；
8. Source commit 后；
9. 更新 SQLite 状态前。

每个位置验证 Resume 结果。

## 4. 数据一致性测试

最终必须满足：

```text
归档前：
Source = Active + ArchiveEligible

归档后：
Source = Active
Archive = 原 Archive + ArchiveEligible
```

且：

```text
Source deleted keys
=
Archive verified keys
```

## 5. 性能指标

V1 不追求最大吞吐，但要求：

- UI 不冻结；
- 内存不随行数线性增长；
- Batch Size 可调整；
- 生产库无长事务；
- DELETE 有批量 COMMIT。

## 6. 生产试运行

顺序：

1. 测试库；
2. 生产 Copy Only；
3. 人工 SQL 校验；
4. 少量 Purge；
5. 扩大范围；
6. 正式运行。
