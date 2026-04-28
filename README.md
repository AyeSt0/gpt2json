<p align="center">
  <img src="docs/assets/hero.png" alt="GPT2JSON - Sub2API / CPA JSON 导出工具" width="100%">
</p>

<h1 align="center">GPT2JSON</h1>

<p align="center">
  面向中文环境的 Sub2API / CPA JSON 导出工具。协议优先、轻量桌面化、本地生成、批次隔离。
</p>

<p align="center">
  <a href="https://github.com/AyeSt0/gpt2json/releases"><img alt="Latest Release" src="https://img.shields.io/github/v/release/AyeSt0/gpt2json?style=for-the-badge&label=release&color=2563EB"></a>
  <a href="https://github.com/AyeSt0/gpt2json/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/AyeSt0/gpt2json/ci.yml?branch=main&style=for-the-badge&label=tests"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/AyeSt0/gpt2json?style=for-the-badge"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="GUI" src="https://img.shields.io/badge/gui-PySide6-7C3AED?style=for-the-badge">
</p>

<p align="center">
  <a href="#-它解决什么问题">解决的问题</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-输入格式">输入格式</a> ·
  <a href="#-输出结构">输出结构</a> ·
  <a href="#-发行包">发行包</a> ·
  <a href="#-路线图">路线图</a>
</p>

---

## ✨ 它解决什么问题

GPT2JSON 把账号文本批量转换为可导入的 **Sub2API JSON** 和 / 或 **CPA 单账号 JSON**。它只在本地生成文件，不会直接写入 Sub2API 后台，适合“先生成、再检查、最后导入”的交付流程。

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| 协议登录 | ✅ 已实现 | 默认走 HTTP/OAuth 流程，不拉起浏览器自动化。 |
| 粘贴 / 文件输入 | ✅ 已实现 | 桌面端可直接粘贴多行，也可导入文本文件。 |
| 自动并发 | ✅ 已实现 | 默认按账号数量自动选择并发，也支持手动输入。 |
| 免登录取码 URL | ✅ 已实现 | 支持 JSON / 文本 / HTML 内 API 自动发现。 |
| Sub2API 导出 | ✅ 已实现 | 生成 `sub2api_accounts.secret.json`。 |
| CPA 导出 | ✅ 已实现 | 一个账号一个 JSON，同时生成 ZIP 包。 |
| 唯一批次目录 | ✅ 已实现 | 每次导出新建 `GPT2JSON_<时间戳>_<编码>/`，不覆盖历史。 |
| 多协议邮箱取码 | 🧭 规划中 | IMAP / Graph / JMAP / POP3 / Provider API。 |

## 🖥️ 桌面界面

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/gui-zh-preview-dark.png">
    <img src="docs/assets/gui-zh-preview.png" alt="GPT2JSON 中文桌面界面预览" width="88%">
  </picture>
</p>

桌面版以中文用户为主：账号输入、导出格式、并发、输出位置、日志诊断都集中在一个窗口里。日志会用序号标记账号阶段，尽量把“正在登录 / 等验证码 / 自动重试 / 已输出到哪里”说清楚。

## 🚀 快速开始

### 桌面版

```bash
python -m pip install -e .[gui]
gpt2json-gui
```

使用步骤：

1. 保持账号格式为 `自动识别（推荐）`；
2. 粘贴账号文本，或导入账号文件；
3. 选择输出根目录；
4. 勾选 `Sub2API JSON`、`CPA JSON`，可单选也可全选；
5. 并发保持 `自动`，必要时再手动调整；
6. 点击 `开始导出`，完成后打开本次结果目录。

### CLI

```bash
gpt2json \
  --input accounts.txt \
  --out-dir output \
  --concurrency 0 \
  --input-format auto
```

从标准输入读取：

```bash
cat accounts.txt | gpt2json --stdin --out-dir output --no-cpa
```

查看版本和帮助：

```bash
gpt2json --version
gpt2json --help
```

## 📥 输入格式

GPT2JSON 的输入解析由 parser 注册表驱动。桌面版下拉栏会展示当前格式和未来预制格式；未实现的格式会置灰，避免误选。

当前版本优先适配 **LDXP Plus7** 的三段式账号格式：

> 当前支持来源：[pay.ldxp.cn/shop/plus7](https://pay.ldxp.cn/shop/plus7)

```text
GPT邮箱----GPT密码----OTP取码源
```

示例：

```text
user@example.test----example-gpt-password----https://otp-service.test/latest?mail={email}
```

| 字段 | 含义 | 注意 |
| --- | --- | --- |
| `GPT邮箱` | GPT/OpenAI 登录邮箱 | 仅作为 GPT 账号使用。 |
| `GPT密码` | GPT/OpenAI 登录密码 | 不是邮箱密码。 |
| `OTP取码源` | 免登录验证码 URL、取码邮箱或其它取码源 | 当前已实现免登录 URL；其它邮箱凭据格式后续独立接入。 |

> 后续新增格式时，会明确区分 `GPT 密码`、`邮箱密码`、`邮箱 app-password`、`access token`、`refresh token` 等字段，避免把不同凭据混在一起。

更多格式扩展说明见 [`docs/input-formats.md`](docs/input-formats.md)。

## 📤 输出结构

每次运行都会在你选择的输出根目录下创建唯一批次目录，不会覆盖旧导出。

```text
output/
└─ GPT2JSON_20260429_043512_a1b2c3/
   ├─ CPA/
   │  └─ <account-email>.json
   ├─ cpa_tokens_20260429_043512_a1b2c3.zip
   ├─ cpa_manifest.json
   ├─ failure_report.safe.json
   ├─ progress.json
   ├─ results.safe.jsonl
   ├─ sub2api_accounts.secret.json
   └─ summary.json
```

| 文件 | 用途 |
| --- | --- |
| `sub2api_accounts.secret.json` | Sub2API 导入用总包。 |
| `CPA/<account-email>.json` | CPA 单账号 token 文件；一个账号一个 JSON。 |
| `cpa_tokens_<批次ID>.zip` | CPA 多账号打包文件，便于整体搬运。 |
| `cpa_manifest.json` | CPA 文件索引，只记录文件列表和脱敏元数据。 |
| `failure_report.safe.json` | 失败诊断报告，不包含原始密码、token 或取码源明文。 |
| `summary.json` | 本次导出统计；包含 `output_root`、`out_dir`、`batch_id`。 |
| `results.safe.jsonl` | 脱敏过程记录，用于排查阶段状态。 |

## 📦 发行包

GitHub Release 提供两类 Windows 产物：

| 文件 | 推荐场景 |
| --- | --- |
| `GPT2JSON-Setup-vX.Y.Z.exe` | 推荐给普通用户。自定义安装外壳 + 标准安装核心。 |
| `GPT2JSON-vX.Y.Z-windows-x64.zip` | 便携使用；解压后直接运行 `GPT2JSON.exe`。 |

<p align="center">
  <img src="docs/assets/installer-preview.png" alt="GPT2JSON 安装器预览" width="82%">
</p>

运行配置保存到 `%LOCALAPPDATA%\GPT2JSON\settings.ini`。GUI 偏好不写入注册表；安装器只创建标准卸载项和快捷方式。如果希望完全免安装，使用 ZIP 便携包即可。

## 🧩 协议后端规划

GPT2JSON 的方向是 **backend-first**：优先沉到 IMAP / Graph / JMAP / POP3 / API 这类可复用协议层，而不是把逻辑写死在某个邮箱品牌名里。

| 后端 | 状态 | 目标 |
| --- | --- | --- |
| HTTP no-login URL | ✅ 已实现 | 免登录取码链接。 |
| External command | ✅ 已实现 | 本地命令扩展自定义取码。 |
| IMAP / IMAP XOAUTH2 | 🧭 规划中 | 邮箱密码、app-password、OAuth token 取码。 |
| Graph | 🧭 规划中 | Graph 兼容邮箱 token 取码。 |
| JMAP | 🧭 规划中 | Fastmail、LuckMail 等 JMAP/API 型邮箱。 |
| POP3 | 🧭 规划中 | 简单邮箱协议兜底。 |
| Provider API | 🧭 规划中 | AtomicMail、LuckMail 等自定义 API 来源。 |

详见 [`docs/mail-backends.md`](docs/mail-backends.md)。

## 🔐 隐私与安全

- 不要把真实账号、密码、token、cookie、导出 JSON、邮箱内容提交到 GitHub。
- 日志、失败报告、manifest 默认只写脱敏信息。
- `*.secret.json`、`output/`、本地构建产物已经加入 `.gitignore`。
- 如果要反馈问题，请使用合成示例或先脱敏。

更多见 [`SECURITY.md`](SECURITY.md) 与 [`docs/privacy.md`](docs/privacy.md)。

## 🗺️ 路线图

- [x] 协议优先 OAuth → JSON 导出
- [x] 中文 GUI：粘贴 / 文件输入、输出格式选择、深浅色主题
- [x] 取消任务、自动重试、失败诊断报告
- [x] 唯一批次输出目录，避免覆盖历史导出
- [ ] IMAP / IMAP XOAUTH2 取码 backend
- [ ] Graph / JMAP / POP3 backend
- [ ] CSV / 表格列映射导入
- [ ] 更细的失败账号重跑入口

## 🛠️ 开发与发版

```bash
git clone https://github.com/AyeSt0/gpt2json.git
cd gpt2json
python -m pip install -e .[dev,gui]
python -m ruff check gpt2json tests scripts
python -m pytest -q
```

重新生成 README 截图和营销图：

```bash
python scripts/generate_docs_assets.py
```

发版前检查：

```bash
python scripts/check_release.py
python -m build
python -m twine check dist/*
```

完整发版流程见 [`docs/release.md`](docs/release.md)。

## 🤝 贡献

欢迎提交新的输入格式、OTP backend、GUI 体验改进和文档修正。请先阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)，并确保测试只使用合成数据。

## 📄 许可证

MIT，详见 [`LICENSE`](LICENSE)。
