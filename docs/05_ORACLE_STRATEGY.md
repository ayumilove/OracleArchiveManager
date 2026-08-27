# Oracle 11g 数据访问与性能策略

## 1. 驱动

使用 Oracle 官方 `python-oracledb`。

PyPI 安装名为 `oracledb`（python-oracledb 官方同源发布，import 同为 `oracledb`；部分企业出口环境拦截全名）。

Oracle 11g 连接建议使用 Thick Mode，并配套兼容 Oracle 11g 的 Oracle Client。

## 2. 批量读取

禁止：

```python
fetchall()
```

大表归档使用：

```python
cursor.arraysize = batch_size
rows = cursor.fetchmany(batch_size)
```

默认：

```text
5000
```

允许配置：

```text
1000 ~ 50000
```

## 3. 批量写入

禁止逐行：

```python
for row in rows:
    execute(...)
```

使用：

```python
executemany(insert_sql, rows)
```

## 4. Oracle 11g 分页

Oracle 11g 不支持 `FETCH FIRST`。

基础模式：

```sql
SELECT *
FROM (
    SELECT t.*
    FROM schema.table_name t
    WHERE <archive_condition>
      AND <batch_key_condition>
    ORDER BY <key_columns>
)
WHERE ROWNUM <= :batch_size
```

其中 `<batch_key_condition>` 由 Keyset 分页生成（见 §5），禁止依赖 OFFSET 或 ROWNUM 倍乘的深分页。

## 5. Batch Selection 与 Keyset 分页

Batch selection 必须满足：

- 可重复：给定相同快照，任一批次数据可重新选出；
- 确定：Resume 与重试不改变批次选择结果；
- 不重不漏：全部批次恰好构成 archive_condition 数据集的一个分区。

采用 Keyset 分页：

```sql
-- 第一批：无 key 条件

-- 后续批次，单键：
WHERE key_column > :last_key

-- 后续批次，复合键（展开写法，11g 兼容）：
WHERE (k1 > :last_k1)
   OR (k1 = :last_k1 AND k2 > :last_k2)
```

规则：

- 每批结束时将该批最大 key 记入 `archive_batch.selection_snapshot`，作为下一批的起点；
- `key_columns` 必须 NOT NULL 且有索引，否则 Analyze 阶段阻断并报错；
- 禁止 OFFSET / SKIP 式深分页（大表深页性能退化为 O(n²)）；
- §4 中的 ROWNUM 仅用于截断单批行数，分页定位全部由 key 条件完成。

## 6. 幂等

目标表必须具备：

- Primary Key；或
- Unique Key；或
- 用户明确指定可唯一识别记录的列。

如果不存在唯一键：

- V1 默认禁止 Purge；
- 可以允许 Copy Only。

## 7. 结构检查

比较：

- COLUMN_NAME
- DATA_TYPE
- DATA_LENGTH（仅非字符类型；字符类型的 DATA_LENGTH 是物理字节数，随字符集与 BYTE/CHAR 语义变化，跨库比较必然误报）
- DATA_PRECISION
- DATA_SCALE
- CHAR_LENGTH（字符类型的容量口径）
- NULLABLE

V1 要求 Source/Target 对应字段一致。

## 8. LOB

CLOB/BLOB 必须单独测试。

V1：

- 支持 CLOB/BLOB 前必须建立自动化测试；
- 未验证的数据类型在 GUI 中显示 Warning；
- 不因为单一表存在 LOB 就默认启用高速批量参数。

## 9. DELETE

DELETE 必须分批提交。

禁止一次：

```sql
DELETE FROM table
WHERE creation_date < :cutoff;
COMMIT;
```

## 10. 索引与统计信息

归档程序只负责数据归档，不默认执行：

- SHRINK SPACE
- MOVE TABLE
- REBUILD INDEX
- DBMS_STATS

V1 可在完成后给出建议，由 DBA 手工执行。

## 11. 目标表创建

任务配置中的“如果不存在则创建”仅作用于目标（归档）库：

- 默认关闭，需用户显式开启；
- DDL 由 Source metadata 生成，仅包含表结构与主键 / 唯一键，不创建普通索引、注释等对象；
- 绝不在生产库执行任何 DDL；
- 创建后必须通过结构检查（§7）方可进入 Copy。
