param(
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distExe = Join-Path $root "dist\GPT2JSON\GPT2JSON.exe"
$script = Join-Path $root "packaging\windows\GPT2JSON.iss"
$releaseDir = Join-Path $root "release"

function Get-ProjectVersion {
    Push-Location $root
    try {
        $version = (& python -c "import gpt2json; print(gpt2json.__version__)" 2>&1)
        if ($LASTEXITCODE -ne 0) { throw ($version -join "`n") }
        $version = ($version | Select-Object -Last 1).Trim()
    }
    finally {
        Pop-Location
    }

    if ([string]::IsNullOrWhiteSpace($version)) {
        throw "无法从 gpt2json.__version__ 读取项目版本。"
    }
    if ($version -notmatch '^\d+(\.\d+){1,3}$') {
        throw "项目版本 '$version' 不是 Inno Setup VersionInfoVersion 支持的数字版本格式（例如 0.1.0）。"
    }
    return $version
}

if (-not (Test-Path $distExe)) {
    throw "未找到 PyInstaller 产物：$distExe。请先构建 dist\GPT2JSON。"
}
if (-not (Test-Path $script)) {
    throw "未找到 Inno Setup 脚本：$script"
}

$scriptText = Get-Content -LiteralPath $script -Raw
$appVersion = Get-ProjectVersion
if (($scriptText -match '(?m)^#define\s+MyAppVersion\s+"([^"]+)"') -and ($Matches[1] -ne $appVersion)) {
    throw "版本不一致：gpt2json.__version__=$appVersion，但 $script 中 MyAppVersion=$($Matches[1])。请同步版本。"
}

$requiredAssets = @(
    (Join-Path $root "gpt2json\assets\gpt2json_icon.ico"),
    (Join-Path $root "packaging\windows\assets\installer-side.bmp"),
    (Join-Path $root "packaging\windows\assets\installer-small.bmp")
)
foreach ($asset in $requiredAssets) {
    if (-not (Test-Path -LiteralPath $asset)) { throw "缺少安装器资源文件：$asset" }
}

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
& $iscc "/DMyAppVersion=$appVersion" $script
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败。" }

$installer = Join-Path $releaseDir "GPT2JSON-Setup-v$appVersion.exe"
if (-not (Test-Path $installer)) {
    throw "安装器编译完成但未找到输出文件：$installer"
}

Get-Item $installer | Select-Object FullName, Length, LastWriteTime
