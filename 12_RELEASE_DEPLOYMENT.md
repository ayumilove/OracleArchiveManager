# 发布与部署

## 1. 发布形式

V1：

```text
OracleArchiveManager.exe
```

推荐 Nuitka 编译。

## 2. 客户端要求

- Windows 10/11 64-bit；
- 网络可访问 Source Oracle；
- 网络可访问 Archive Oracle；
- Oracle Client（如 Thick Mode 需要）。

## 3. 本地文件

建议：

```text
%APPDATA%/OracleArchiveManager/
├── archive_manager.db
├── logs/
├── config/
└── cache/
```

程序目录不保存业务数据。

## 4. 升级

SQLite 必须支持 migration。

版本：

```text
1.0.0
1.0.1
1.1.0
```

启动时：

1. 备份 control db；
2. 检查 schema version；
3. 执行 migration；
4. 启动程序。

## 5. 日志

文件日志按天滚动：

```text
oracle_archive_2026-08-27.log
```

保留 30/90 天可配置。

## 6. 配置备份

提供：

- Export Config；
- Import Config。

默认不导出数据库密码。

## 7. 发布前检查

- 单元测试通过；
- Integration Test；
- Recovery Test；
- Nuitka Build；
- Windows Defender 检查；
- Oracle 11g Smoke Test；
- Release Notes。
