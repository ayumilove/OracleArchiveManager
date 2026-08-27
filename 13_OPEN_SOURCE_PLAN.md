# 开源规划建议

## 1. 是否值得开源

项目定位不追求大而全，而是：

> Lightweight Oracle historical data archive and safe purge tool.

差异化：

- Oracle 优先；
- Oracle 11g 兼容；
- Oracle → Oracle；
- GUI；
- Batch Copy；
- Verify；
- Resume；
- Manual Safe Purge；
- Offline First。

## 2. 开源前建议

内部至少稳定运行 3~6 个月，并完成：

- 中断恢复；
- LOB；
- 联合主键；
- 大表性能；
- 安全审计；
- 安装包。

## 3. 开源边界

可开源：

- Archive Core；
- Oracle Repository；
- PySide6 GUI；
- SQLite Control DB。

可独立保留：

- 企业内部配置；
- License Service；
- 内部数据库连接；
- 特定业务规则。

## 4. 许可证

优先考虑：

- Apache-2.0；或
- MIT。

如果未来考虑商业版，需要在正式发布前确认许可策略。

## 5. README 必须明确

- 生产环境使用前必须测试；
- 建议先 Copy Only；
- 建议有数据库备份；
- Purge 是高风险操作；
- 软件不保证替代 DBA 判断。
