# Changelog

本项目使用类似 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 的格式记录重要变化。

## [Unreleased]

### Added

- GUI smoke tests for headless initialization and input-state behavior.
- GUI settings persistence, output-directory validation, log copy/clear actions, and running-close protection.

### Changed

- GUI preflight now reports skipped rows and separates selected output formats from already generated files.

## [0.1.0] - 2026-04-27

### Added

- 协议优先 OAuth 导出流程。
- 并发批处理引擎。
- Sub2API / CPA JSON 导出。
- PySide6 轻量桌面 GUI。
- GUI 支持账号文件或直接粘贴文本输入，导出格式可单选或多选。
- GUI 支持账号格式选择，当前默认自动识别，后续格式由 parser 注册表扩展。
- GUI 下拉栏展示未来输入格式预制项，未实现项置灰禁用，避免误选。
- 并发数默认自动，CLI 支持 `--stdin` 管道输入。
- 输入格式 parser 注册表与 auto-detect 入口。
- Backend-first 邮箱 OTP 注册表骨架，围绕 IMAP / Graph / JMAP / POP3 / API 扩展。
- HTTP no-login OTP 支持 HTML 前端内 API 自动发现，避免从脚本常量误取验证码。
- 协议登录默认指纹更新为 `chrome136`，并补齐更接近浏览器导航 / JSON 请求的默认头。
- GUI 输入来源、导出格式、输出文件和运行状态联动重构；浅色 / 深色预览与图标素材更新。
- GitHub-ready 项目元数据、测试、文档和模板。
