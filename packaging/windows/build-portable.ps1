param(
    [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distDir = Join-Path $root "dist\GPT2JSON"
$buildDir = Join-Path $root "build\GPT2JSON"
$launcher = Join-Path $root "scripts\launch_gui.py"
$assetDir = Join-Path $root "gpt2json\assets"
$icon = Join-Path $assetDir "gpt2json_icon.ico"

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "未找到 GUI 启动入口：$launcher"
}
if (-not (Test-Path -LiteralPath $icon)) {
    throw "未找到程序图标：$icon"
}

function Remove-RepoChild {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理仓库外路径：$resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

if ($Clean) {
    Remove-RepoChild $distDir
    Remove-RepoChild $buildDir
}

Push-Location $root
try {
    & pyinstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name GPT2JSON `
        --paths "$root" `
        --hidden-import gpt2json.gui `
        --collect-submodules gpt2json `
        --icon "$icon" `
        --add-data "$assetDir;gpt2json/assets" `
        "$launcher"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败。"
    }
}
finally {
    Pop-Location
}

$exe = Join-Path $distDir "GPT2JSON.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "PyInstaller 构建结束但未找到产物：$exe"
}

$pyz = Get-ChildItem -LiteralPath (Join-Path $root "build\GPT2JSON") -Filter "PYZ-*.pyz" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pyz) {
    throw "未发现 PyInstaller PYZ 归档，便携包可能缺模块。"
}

$archiveList = & pyi-archive_viewer --list --brief $pyz.FullName
if ($LASTEXITCODE -ne 0) {
    throw "无法检查 PyInstaller PYZ 归档内容。"
}
if (-not ($archiveList | Select-String -Pattern '^\s+gpt2json\.gui$' -Quiet)) {
    throw "PyInstaller 产物缺少 gpt2json.gui；请检查 --paths / hidden import / collect-submodules 配置。"
}

Get-Item -LiteralPath $exe | Select-Object FullName, Length, LastWriteTime
