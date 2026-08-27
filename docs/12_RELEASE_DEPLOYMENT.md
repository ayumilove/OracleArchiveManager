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

## 8. CI/CD（GitHub Actions）

工作流位于 `.github/workflows/`：

| 工作流 | 触发 | 内容 |
|---|---|---|
| `ci.yml` | push 到 main / PR | uv 安装依赖 + 运行单元测试 |
| `release.yml` | push 标签 `v*.*.*` | 注入标签版本号 → 单元测试 → Nuitka 编译单文件 exe → 创建 GitHub Release |

发布流程：

```text
git tag v0.2.0
git push origin v0.2.0
# Actions 自动编译并生成 Release，产物：OracleArchiveManager.exe
```

要点：

- 版本号以标签为准，流水线自动写回 `__init__.py` 后再编译；
- Release 必须附带 `OracleArchiveManager.exe` 产物，否则客户端 OTA 只能引导手动下载；
- CI 使用官方 PyPI 源（`UV_DEFAULT_INDEX`），不受本地清华镜像配置影响。

## 9. 自动更新（OTA）

- 启动时后台查询 GitHub Releases `latest` 接口，比对本地版本；
- 发现新版：弹出引导对话框，展示发布说明；
  - 打包 exe 环境：一键下载新版 → 退出程序 → 更新脚本替换 exe → 自动重启；
  - 源码运行环境：仅引导打开发布页手动下载；
- 网络失败静默降级，不影响主流程；
- 可在系统设置关闭「启动时自动检查更新」，也可在「关于」中手动检查。

实现：`services/update_checker.py`（纯标准库）+ `ui/update_dialog.py`。
