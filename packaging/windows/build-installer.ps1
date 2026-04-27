param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distExe = Join-Path $root "dist\GPT2JSON\GPT2JSON.exe"
$script = Join-Path $root "packaging\windows\GPT2JSON.iss"
$releaseDir = Join-Path $root "release"

if (-not (Test-Path $distExe)) {
    throw "未找到 PyInstaller 产物：$distExe。请先构建 dist\GPT2JSON。"
}
if (-not (Test-Path $script)) {
    throw "未找到 Inno Setup 脚本：$script"
}

$scriptText = Get-Content -LiteralPath $script -Raw
if ($scriptText -notmatch '(?m)^#define\s+MyAppVersion\s+"([^"]+)"') {
    throw "无法从 Inno Setup 脚本读取 MyAppVersion：$script"
}
$appVersion = $Matches[1]

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

$command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
$candidates = @(
    @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }
)

if ($command) {
    $iscc = $command.Source
} elseif ($candidates.Count -gt 0) {
    $iscc = [string]$candidates[0]
} else {
    throw "未找到 Inno Setup 编译器 ISCC.exe。请安装 Inno Setup 6 后重试。"
}

Write-Host "使用版本: $appVersion"
Write-Host "使用 Inno Setup: $iscc"
Write-Host "编译脚本: $script"
& $iscc $script
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败。" }

$installer = Join-Path $releaseDir "GPT2JSON-Setup-v$appVersion.exe"
if (-not (Test-Path $installer)) {
    throw "安装器编译完成但未找到输出文件：$installer"
}

Get-Item $installer | Select-Object FullName, Length, LastWriteTime
