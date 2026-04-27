# Changelog

本项目使用类似 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 的格式记录重要变化。

## [0.1.0] - 2026-04-27

### Added

- 协议优先 OAuth 导出流程。
- 并发批处理引擎。
- Sub2API / CPA JSON 导出。
- PySide6 轻量桌面 GUI。
- GUI 支持账号文件或直接粘贴文本输入，导出格式可单选或多选。
- GUI 支持账号格式选择，当前默认自动识别，后续格式由 parser 注册表扩展。
- 并发数默认自动，CLI 支持 `--stdin` 管道输入。
- 输入格式 parser 注册表与 auto-detect 入口。
- Backend-first 邮箱 OTP 注册表骨架，围绕 IMAP / Graph / JMAP / POP3 / API 扩展。
- GitHub-ready 项目元数据、测试、文档和模板。
