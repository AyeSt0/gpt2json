<p align="center">
  <img src="docs/assets/hero.png" alt="GPT2JSON - Sub2API / CPA JSON 导出工具" width="100%">
</p>

<h1 align="center">GPT2JSON</h1>

<p align="center">
  面向中文账号交付场景的 <b>Sub2API / CPA JSON 导出工具</b>。粘贴账号文本，本地生成可导入 JSON，不直接写入后台。
</p>

<p align="center">
  <a href="https://github.com/AyeSt0/gpt2json/releases/latest"><img alt="最新版本" src="https://img.shields.io/badge/version-v0.1.7-60A5FA?style=for-the-badge"></a>
  <a href="https://github.com/AyeSt0/gpt2json/releases/latest"><img alt="Windows" src="https://img.shields.io/badge/Windows-%E5%AE%89%E8%A3%85%E5%8C%85-38BDF8?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/AyeSt0/gpt2json/releases/latest"><img alt="Portable ZIP" src="https://img.shields.io/badge/ZIP-%E4%BE%BF%E6%90%BA%E7%89%88-8B5CF6?style=for-the-badge&logo=github&logoColor=white"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/AyeSt0/gpt2json?style=for-the-badge"></a>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#当前支持">当前支持</a> ·
  <a href="#输出结果">输出结果</a> ·
  <a href="#界面预览">界面预览</a> ·
  <a href="#常见问题">常见问题</a> ·
  <a href="#开发者">开发者</a>
</p>

---

## 这是什么

GPT2JSON 用来把已交付的账号文本转换成两类本地 JSON 文件：

- **Sub2API JSON**：一个批次一个总包。
- **CPA JSON**：一个账号一个 JSON，统一放进独立文件夹。

它不负责把账号直接导入 Sub2API 后台，而是先把文件稳定生成出来，方便你检查、归档和再导入。

## 快速开始

### 下载使用（推荐）

前往 [Releases](https://github.com/AyeSt0/gpt2json/releases/latest) 下载：

| 文件 | 适合谁 |
| --- | --- |
| `GPT2JSON-Setup-v0.1.7.exe` | 普通用户，推荐安装版。 |
| `GPT2JSON-v0.1.7-windows-x64.zip` | 免安装使用，解压后运行。 |

使用流程：

1. 打开 GPT2JSON。
2. 粘贴账号文本，或导入 `.txt` 文件。
3. 选择导出格式：`Sub2API`、`CPA`，也可以两个都选。
4. 点击开始，等待任务完成。
5. 打开结果目录，使用生成的 JSON 文件导入目标系统。

### 从源码运行

```bash
git clone https://github.com/AyeSt0/gpt2json.git
cd gpt2json
python -m pip install -e .[gui]
gpt2json-gui
```

CLI 示例：

```bash
gpt2json --input accounts.txt --out-dir output --input-format auto
```

## 当前支持

目前暂时只支持 **卡网 LDXP Plus7** 提供的账号格式：

```text
GPT邮箱----GPT登录密码----免登录取码源
```

格式来源：[`https://pay.ldxp.cn/shop/plus7`](https://pay.ldxp.cn/shop/plus7)

| 字段 | 含义 |
| --- | --- |
| `GPT邮箱` | GPT / OpenAI 登录邮箱。 |
| `GPT登录密码` | GPT / OpenAI 登录密码，不是邮箱密码。 |
| `免登录取码源` | 用于获取邮箱验证码的免登录链接或取码源。 |

示例为合成数据：

```text
user@example.test----example-gpt-password----https://otp-service.test/latest?mail={email}
```

> 后续格式适配敬请期待。后续会继续扩展 IMAP / Graph / JMAP / POP3 / API 等取码方式，以及更多常见账号文本格式；不同格式里的 GPT 密码、邮箱密码、邮箱令牌、API token 会明确区分，不会混用字段语义。

## 主要能力

| 能力 | 说明 |
| --- | --- |
| 粘贴 / 文件导入 | 支持直接粘贴多行账号，也支持导入 `.txt`。 |
| 自动识别格式 | 默认自动识别；暂未支持的格式会在界面中置灰展示。 |
| 协议优先登录 | 优先走协议流程，尽量减少浏览器自动化依赖。 |
| 按需取验证码 | 大多数账号只走账密；只有服务端要求时才进入取码流程。 |
| 自动并发 | 默认自动选择并发，也可以在高级选项中手动调整。 |
| 自动重试 / 自动补救 | 网络波动、取码延迟、旧验证码等可恢复问题会尽量自动处理。 |
| 导出校验 | 完成后会提示导出的 Sub2API / CPA 文件是否可导入。 |
| 批次隔离 | 每次任务创建唯一结果目录，避免覆盖旧文件。 |

## 输出结果

桌面版默认输出到程序目录下的 `output/`。如果你手动选择过输出目录，软件会记住你的选择。

每次运行都会生成一个唯一批次目录：

```text
output/
└─ GPT2JSON_20260429_043512_a1b2c3/
   ├─ sub2api_accounts.secret.json
   ├─ CPA_20260429_043512_a1b2c3/
   │  ├─ user01@example.test.json
   │  └─ user02@example.test.json
   ├─ failed_rerun.secret.txt        # 仅可恢复失败时生成
   └─ _diagnostics/                  # 排障信息，普通导入一般不用打开
```

| 路径 | 用途 |
| --- | --- |
| `sub2api_accounts.secret.json` | Sub2API 导入用总包。 |
| `CPA_<批次>/` | CPA 单账号 JSON 文件夹，一个账号一个 JSON。 |
| `failed_rerun.secret.txt` | 可恢复失败账号清单，用于自动补跑或手动重跑失败账号。 |
| `_diagnostics/` | 脱敏诊断信息，方便排查失败原因。 |

普通用户通常只需要使用 `sub2api_accounts.secret.json` 和 / 或 `CPA_<批次>/`。

## v0.1.7 更新重点

- 安装器支持识别已安装版本，并自动进入升级 / 修复模式。
- 升级安装前会自动关闭旧版窗口，避免新旧版本同时运行。
- 客户端增加单实例保护，同一用户环境下只允许打开一个窗口。
- 输出目录更清晰：导入文件放在主目录，诊断信息统一放到 `_diagnostics/`。
- 每次任务和 CPA 文件夹都使用唯一批次名，避免覆盖历史结果。
- 可恢复失败会自动重试、自动补救，批次结束后还能自动补跑失败账号。
- 取码源偶发空响应、旧验证码、验证码延迟等情况处理更稳定。
- 日志文案更清楚，能看到账号序号、当前阶段和补救状态。

## 界面预览

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/gui-zh-preview-dark.png">
    <img src="docs/assets/gui-zh-preview.png" alt="GPT2JSON 中文桌面界面预览" width="88%">
  </picture>
</p>

<p align="center">
  <img src="docs/assets/installer-preview.png" alt="GPT2JSON 安装器预览" width="82%">
</p>

## 常见问题

### 它会直接导入 Sub2API 吗？

不会。GPT2JSON 只生成本地 JSON 文件。你可以先检查结果，再导入目标系统。

### CPA 是一个文件还是多个文件？

CPA 是 **一个账号一个 JSON**。所有 CPA JSON 会放在唯一的 `CPA_<批次>/` 文件夹里。

### 为什么会有 `_diagnostics/`？

它是排障目录，里面是脱敏日志、失败报告和统计信息。普通导入时通常不用打开。

### 账号失败会自动重跑吗？

会尽量自动处理可恢复失败，例如网络波动、验证码延迟、旧验证码、临时接口异常等。账号停用、锁定、不存在、凭据错误等终态问题不会无意义反复重跑。

### 会保存我的账号密码吗？

导出结果和失败重跑清单会保存在你本机选择的输出目录中，其中 `*.secret.*` 文件属于敏感文件，请自行保管，不要上传到 GitHub 或发给无关人员。项目默认把这些文件加入 `.gitignore`。

## 路线图

- [x] Sub2API JSON 导出
- [x] CPA 单账号 JSON 文件夹导出
- [x] 中文 GUI、深浅色主题、安装器和便携包
- [x] 自动并发、自动重试、自动补救、批次级自动补跑
- [x] 唯一批次目录，避免覆盖旧结果
- [ ] IMAP / IMAP XOAUTH2 取码 backend
- [ ] Graph / JMAP / POP3 backend
- [ ] CSV / 表格列映射导入
- [ ] 更多常见账号文本格式

## 隐私与安全

- 不要把真实账号、密码、token、cookie、导出 JSON、邮箱内容提交到 GitHub。
- 日志和诊断报告默认尽量脱敏。
- `*.secret.json`、`*.secret.txt`、`output/`、构建产物已加入 `.gitignore`。
- 反馈问题时建议使用合成示例，或先完成脱敏。

更多说明：[`SECURITY.md`](SECURITY.md) · [`docs/privacy.md`](docs/privacy.md)

## 文档

| 文档 | 内容 |
| --- | --- |
| [`docs/input-formats.md`](docs/input-formats.md) | 输入格式、字段语义和扩展约定。 |
| [`docs/mail-backends.md`](docs/mail-backends.md) | IMAP / Graph / JMAP / POP3 / API 取码规划。 |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | 常见失败和输出目录说明。 |
| [`docs/project-structure.md`](docs/project-structure.md) | 仓库结构和维护约定。 |
| [`docs/release.md`](docs/release.md) | 打包与发版流程。 |

## 开发者

<details>
<summary>本地开发、测试和打包</summary>

```bash
python -m pip install -e .[dev,gui,release]
python -m ruff check gpt2json tests scripts
python -m pytest -q
```

启动 GUI：

```bash
gpt2json-gui
```

生成文档素材：

```bash
python scripts/generate_docs_assets.py
```

发版检查：

```bash
python scripts/check_release.py --require-assets
```

Windows 打包流程见 [`docs/release.md`](docs/release.md)。

</details>

## 许可证

MIT，详见 [`LICENSE`](LICENSE)。
