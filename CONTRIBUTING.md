# 贡献指南

欢迎改进 GPT2JSON。项目当前以中文桌面体验、输入格式扩展和 OTP backend 为主线。

## 开发环境

```bash
git clone https://github.com/AyeSt0/gpt2json.git
cd gpt2json
python -m pip install -e .[dev,gui]
python -m ruff check gpt2json tests scripts
python -m pytest -q
```

如修改 README 图片或截图：

```bash
python scripts/generate_docs_assets.py
```

## 提交前检查

- [ ] 没有提交真实账号、密码、token、cookie、导出 JSON、邮件内容或本地日志。
- [ ] 新增 / 修改逻辑已有测试覆盖。
- [ ] `python -m ruff check gpt2json tests scripts` 通过。
- [ ] `python -m pytest -q` 通过。
- [ ] 修改用户可见行为时已更新 README / docs / CHANGELOG。
- [ ] 修改版本或打包逻辑时已运行 `python scripts/check_release.py`。

## 代码方向

### 输入格式

1. 在 `gpt2json/parsing.py` 中新增 parser。
2. 注册到 `INPUT_FORMATS`。
3. 明确区分凭据：
   - `password` / `gpt_password`：GPT/OpenAI 登录密码；
   - `email_credential_kind`：邮箱凭据类型；
   - `email_password`：邮箱密码或 app-password；
   - `email_token`：邮箱 access token；
   - `email_refresh_token`：邮箱 refresh token。
4. 在 `tests/test_parsing.py` 补合成测试。

### OTP backend

- 优先实现通用能力：IMAP / Graph / JMAP / POP3 / API。
- provider/domain 只作为 backend 排序 hint，不要写进 OAuth 登录主流程。
- 新 backend 需要声明支持的凭据类型、超时策略和脱敏日志策略。
- 使用合成数据测试，不依赖真实邮箱账号。

### GUI

- 中文优先，避免用户理解成本。
- 保持轻量：一个主窗口完成输入、导出、日志和结果定位。
- 深浅色主题都需要检查。
- 窗口缩放、不同 DPI 和不同分辨率下不能出现明显布局断裂。

## 分支与 PR

推荐从 `main` 拉分支：

```bash
git checkout -b codex/your-change
```

PR 描述请包含：

- 做了什么；
- 为什么这样做；
- 怎么验证；
- 是否影响输出格式 / Release / GUI 截图。
