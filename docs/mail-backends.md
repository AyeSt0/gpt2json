# 邮箱 OTP backend 规划

GPT2JSON 的 OTP 获取是 **backend-first**。核心抽象是 IMAP、Graph、JMAP、POP3、API 这类能力；provider/domain 检测只用来排序 backend 候选，不进入 OAuth 登录主流程。

## Backend 注册表

`gpt2json/mail_backends.py` 定义能力注册表：

| Backend | 状态 | 凭据类型 | 用途 |
| --- | --- | --- | --- |
| HTTP 免登录 URL | 已实现 | url | 请求 JSON/text 接口并提取 6 位验证码，支持 `{email}` 模板。 |
| 外部命令 | 已实现 | command | 调用外部脚本/命令获取验证码。 |
| IMAP | 规划中 | password、app_password | 通用邮箱轮询和邮件搜索。 |
| IMAP XOAUTH2 | 规划中 | token、refresh_token、oauth2 | token 型 IMAP 访问。 |
| Graph | 规划中 | token、refresh_token、oauth2 | Graph 兼容邮箱查询。 |
| JMAP | 规划中 | token、app_password、api_key | JMAP 兼容邮箱查询。 |
| POP3 | 规划中 | password、app_password | 简单邮箱访问兜底。 |
| API | 规划中 | token、refresh_token、cookie、api_key、password、app_password | 自定义 provider API 接入位。 |

每个 backend 声明自己接受的凭据类型。`BackendPlan` 会根据当前账号行的邮箱凭据，选择第一个支持的候选 backend。

## Domain/provider hint

`gpt2json/mail_providers.py` 是次级提示层，只负责把域名映射到有序 backend 列表：

- token 型邮箱可优先尝试 `Graph` 或 `IMAP XOAUTH2`；
- app password 型邮箱可优先尝试 `IMAP` 或 `JMAP`；
- 普通邮箱可尝试 `IMAP` 再 `POP3`；
- 自定义服务可优先尝试 `API`，再回退协议 backend。

这样可以把 provider 差异限制在 hint 层，真正实现尽量沉到可复用的 backend。

## Adapter 要求

一个 backend adapter 应该：

1. 接收 `AccountRow` 或 mailbox context；
2. 不修改 GPT 凭据；
3. 复用全局 timeout / interval；
4. 复用 `gpt2json/otp.py` 中的验证码提取函数；
5. 不输出或记录敏感凭据；
6. 使用合成数据补单元测试；
7. 在 `mail_backends.py` 中声明状态和支持的凭据类型。

## 推荐实现顺序

1. IMAP：支持 app-password/password。
2. IMAP XOAUTH2：支持 token/refresh-token。
3. Graph：支持 token/refresh-token。
4. JMAP：适合 JMAP 能力更完整的邮箱。
5. POP3：作为简单兜底。
6. API：接入 service-specific token/cookie 格式。
