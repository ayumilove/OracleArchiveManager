# 安全与防误操作设计

## 1. 基本原则

生产库保护优先于归档速度。

## 2. 权限分离

推荐账号：

### Source Reader

```text
SELECT
```

用于：

- Analyze
- Copy
- Verify Source

### Source Purger

```text
SELECT
DELETE
```

仅 Purge 阶段使用。

### Archive Writer

```text
SELECT
INSERT
UPDATE（如幂等策略需要）
```

## 3. 默认行为

默认：

```text
Copy Only / Manual Purge
```

V1 不提供无提示自动 Purge。

## 4. Purge 前置条件

必须全部满足：

- Run Copy 完成；
- Batch = VERIFIED；
- Source/Target metadata compatible；
- Verify result PASS；
- 用户显式确认；
- 当前连接确认为生产库；
- DELETE 权限可用。

## 5. 禁止行为

程序不得：

- DROP TABLE；
- TRUNCATE 生产表；
- 自动修改业务表；
- 自动禁用约束；
- 自动删除索引；
- 在结构校验失败后继续；
- 在目标库不可用时删除源数据。

## 6. 审计

记录：

- 谁执行；
- 哪个连接；
- 哪个 Schema/Table；
- Run ID；
- Cutoff；
- Copy 数量；
- Verify 数量；
- Delete 数量；
- 开始/结束时间；
- 错误信息。

## 7. 凭据

V1 采用 Windows Credential Manager（keyring 库实现）。

SQLite 不保存明文密码，仅保存 credential_ref。

## 8. 在线授权（非归档核心）

如产品未开源阶段需要使用控制，可独立实现 License Service。

授权系统不得：

- 删除业务数据；
- 中断正在执行的数据库事务；
- 到期后破坏现有配置。

建议到期进入只读模式。
