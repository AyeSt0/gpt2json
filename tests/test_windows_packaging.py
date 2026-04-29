from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_exposes_default_names_only():
    inno = (ROOT / "packaging" / "windows" / "GPT2JSON.iss").read_text(encoding="utf-8-sig")
    wrapper_builder = (ROOT / "packaging" / "windows" / "build-art-installer.ps1").read_text(encoding="utf-8")
    uninstaller_builder = (ROOT / "packaging" / "windows" / "build-art-uninstaller.ps1").read_text(encoding="utf-8")
    release_check = (ROOT / "scripts" / "check_release.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    portable_builder = (ROOT / "packaging" / "windows" / "build-portable.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "OutputBaseFilename=GPT2JSON-CoreSetup-v{#MyAppVersion}" in inno
    assert "UninstallFilesDir={app}\\.uninstall" in inno
    assert 'Source: "packaging\\windows\\build\\GPT2JSON-Uninstall.exe"' in inno
    assert "WrapperUninstaller := ExpandConstant('{app}\\GPT2JSON-Uninstall.exe')" in inno
    assert "RegWriteStringValue(HKCU, UninstallKey, 'InstallLocation', ExpandConstant('{app}'))" in inno
    assert "RegWriteStringValue(HKCU, UninstallKey, 'DisplayVersion', '{#MyAppVersion}')" in inno
    assert "release\\GPT2JSON-Setup-v$appVersion.exe" in wrapper_builder
    assert "packaging\\windows\\build\\GPT2JSON-CoreSetup-v$appVersion.exe" in wrapper_builder
    assert 'if ($sourceText -notmatch [regex]::Escape(\'"GPT2JSON-CoreSetup-" + Version + ".exe"\'))' in wrapper_builder
    assert 'Join-Path $outDir "GPT2JSON-Uninstall.exe"' in uninstaller_builder
    assert "GPT2JSON-ArtSetup-v{version}.exe" not in release_check
    assert '"release/GPT2JSON-ArtSetup' not in workflow
    assert "GPT2JSON-ArtSetup" not in readme
    assert ".\\packaging\\windows\\build-portable.ps1" in workflow
    assert '--paths "$root"' in portable_builder
    assert "--hidden-import gpt2json.gui" in portable_builder
    assert "--collect-submodules gpt2json" in portable_builder
    assert "gpt2json\\.gui" in portable_builder


def test_art_installer_detects_existing_install_for_upgrade_mode():
    source = (ROOT / "packaging" / "windows" / "artsetup" / "ArtSetup.cs").read_text(encoding="utf-8-sig")

    assert "InstalledAppInfo.Detect()" in source
    assert "CurrentVersion\\Uninstall\\{F3E03F2D-1CB1-4A63-98D1-0E19E1E20321}_is1" in source
    assert 'ReadString(key, "InstallLocation")' in source
    assert 'ReadString(key, "DisplayVersion")' in source
    assert 'Name = "ModeTitleText"' in source
    assert 'Name = "InstallPathLabel"' in source
    assert 'title.Text = sameVersion ? "修复" : "升级"' in source
    assert '将覆盖升级到 " + Version' in source


def test_public_uninstaller_wrapper_delegates_to_private_inno_core():
    source = (ROOT / "packaging" / "windows" / "artsetup" / "ArtUninstall.cs").read_text(encoding="utf-8-sig")

    assert 'namespace GPT2JSON.Uninstall' in source
    assert 'Path.Combine(appDir, ".uninstall", "unins000.exe")' in source
    assert 'Path.Combine(tempDir, "GPT2JSON-Uninstall.exe")' in source
    assert "GPT2JSON-ArtUninstall.exe" not in source
