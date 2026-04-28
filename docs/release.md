# 发版流程

本文档记录 GPT2JSON 的 GitHub Release 流程。目标是让每次发布都能复现、可校验、不会带入本地账号数据。

## 版本号

版本号需要同步：

- `gpt2json/__init__.py`：`__version__`
- `packaging/windows/GPT2JSON.iss`：`MyAppVersion`
- `CHANGELOG.md`：新增 `## [X.Y.Z] - YYYY-MM-DD`

`python scripts/check_release.py` 会检查 Python 包版本、Inno Setup 版本和 CHANGELOG 标题是否一致。

## 本地检查

```powershell
python -m pip install -e .[dev,gui,release]
python scripts/generate_docs_assets.py
python -m ruff check gpt2json tests scripts
python -m pytest -q
python scripts/check_release.py
python -m build
python -m twine check dist/*
```

如需本地构建 Windows 安装包：

```powershell
pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name GPT2JSON `
  --icon gpt2json/assets/gpt2json_icon.ico `
  --add-data "gpt2json/assets;gpt2json/assets" `
  scripts/launch_gui.py

.\packaging\windows\build-installer.ps1
Compress-Archive -Path dist\GPT2JSON\* -DestinationPath release\GPT2JSON-vX.Y.Z-windows-x64.zip -Force
python scripts/check_release.py --require-assets
```

## GitHub Release

1. 确认 `main` 分支 CI 通过。
2. 创建 tag：

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

3. GitHub Actions 会自动构建：
   - `gpt2json-X.Y.Z-py3-none-any.whl`
   - `gpt2json-X.Y.Z.tar.gz`
   - `GPT2JSON-Setup-vX.Y.Z.exe`
   - `GPT2JSON-vX.Y.Z-windows-x64.zip`

4. Release 发布后，下载资产并校验：

   ```powershell
   python scripts/check_release.py --require-assets
   ```

## 不应进入 Release 的内容

- `output/` 下的本地导出结果；
- 真实账号、密码、token、cookie；
- 本地日志、缓存、测试账号文件；
- 未脱敏的 `*.secret.json`。

## 回滚

如果发布后发现严重问题：

1. 在 Release 页面标记说明；
2. 删除或下架有问题的资产；
3. 修复后发布新的 patch 版本，例如 `v0.1.3`，不要复用旧 tag。
