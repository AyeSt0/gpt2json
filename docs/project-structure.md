# 项目层级说明

GPT2JSON 的仓库层级按“产品文档 / 核心代码 / 打包发布 / 测试验证”拆分。普通开发只需要关注 `gpt2json/`、`tests/` 和 `docs/`。

```text
gpt2json/
├─ .github/                    # GitHub Issue / PR 模板与 CI / Release workflow
├─ docs/                       # 中文产品文档、排障文档、截图和路线图
│  └─ assets/                  # README 与文档使用的图片素材
├─ gpt2json/                   # Python 包源码
│  ├─ assets/                  # GUI 图标、状态图标、主题按钮等运行时素材
│  ├─ __main__.py              # `python -m gpt2json` 入口
│  ├─ cli.py                   # CLI 入口
│  ├─ engine.py                # 批量导出引擎：并发、重试、输出目录
│  ├─ formats.py               # Sub2API / CPA JSON 构建与校验
│  ├─ gui.py                   # PySide6 中文桌面界面
│  ├─ gui_file_dialog.py       # 非原生文件选择器中文化与样式
│  ├─ gui_log_style.py         # GUI 日志颜色与分类规则
│  ├─ gui_paths.py             # GUI 设置路径、默认输出目录和单实例锁路径
│  ├─ gui_resources.py         # GUI 应用常量与素材路径
│  ├─ gui_text_menu.py         # 输入框 / 日志框中文右键菜单
│  ├─ gui_theme.py             # 深浅色主题 token
│  ├─ gui_widgets.py           # 拖拽输入、统计卡片、输出行等小型控件
│  ├─ mail_backends.py         # 取码实现能力抽象（内部）
│  ├─ mail_providers.py        # 号商/邮箱来源与取码实现排序提示
│  ├─ models.py                # 批处理与登录结果数据模型
│  ├─ oauth.py                 # OAuth 参数、PKCE 与 token 辅助函数
│  ├─ otp.py                   # 免登录取码源解析与验证码提取
│  ├─ parsing.py               # 输入格式识别与字段解析
│  ├─ protocol.py              # 协议登录与 OAuth JSON 交换
│  └─ updater.py               # GitHub Release 更新检查
├─ packaging/
│  └─ windows/                 # Windows 便携包、安装器和卸载器构建脚本
│     ├─ artsetup/             # 自定义安装器 / 卸载器壳层源码
│     └─ assets/               # 安装器侧图、小图和设计源图
├─ scripts/                    # 维护脚本：发版检查、清理本地产物、文档素材生成、GUI launcher
├─ tests/                      # pytest 回归测试
├─ CHANGELOG.md                # 版本变更记录
├─ pyproject.toml              # Python 包配置、依赖和工具配置
└─ README.md                   # 面向用户的中文首页
```

## 本地生成目录

以下目录只属于本机开发 / 打包过程，默认不提交到 Git：

| 路径 | 来源 | 说明 |
| --- | --- | --- |
| `build/` | PyInstaller / Python build | 临时构建目录，可随时删除。 |
| `dist/` | PyInstaller | 便携版程序目录，可重新生成。 |
| `release/` | 本地打包 | 本地 release assets 暂存目录；GitHub Release 以页面资产为准。 |
| `output/` | GUI / CLI 导出 | 用户导出的 JSON 和诊断目录，可能含敏感 token，不提交。 |
| `GPT2JSON_*/` | 误选仓库根目录时的导出批次 | 用户结果目录，不提交。 |
| `CPA_*/` | CPA 单账号 JSON 目录 | 可能含可用 token，不提交。 |
| `_diagnostics/` | 导出诊断目录 | 脱敏诊断为主，但仍按本地输出处理，不提交。 |
| `*.egg-info/` | editable install / build | Python 包元数据缓存，可重新生成。 |
| `.pytest_cache/`、`.ruff_cache/` | 测试 / lint | 工具缓存，可重新生成。 |

如果本地看起来“很乱”，通常是这些生成目录残留造成的；仓库的可维护结构以上面的已跟踪目录为准。

## 维护约定

- 真实生效的 workflow 只放在 `.github/workflows/`，不要再复制到 `docs/`，避免两份配置漂移。
- README 放产品视角和下载说明；细节规范放到 `docs/`。
- 打包脚本统一放在 `packaging/windows/`，不要把安装器临时产物提交到源码目录。
- 清理本地生成物优先用 `python scripts/clean_workspace.py --release-old` 预览，再加 `--apply` 执行。
- 新增输入格式优先改 `parsing.py` 并补 `tests/test_parsing.py`。
- 新增导出格式优先改 `formats.py` / `engine.py` 并补 `tests/test_formats.py`、`tests/test_engine.py`。
- GUI 后续如果继续膨胀，建议按“组件 / 对话框 / 样式 / 任务 worker”拆分，但不要在临近发布时大拆，避免引入界面回归。
