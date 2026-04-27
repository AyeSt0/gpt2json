$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$installerScript = Join-Path $root "packaging\windows\GPT2JSON.iss"
if (-not (Test-Path $installerScript)) { throw "未找到 Inno Setup 脚本：$installerScript" }

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
        throw "项目版本 '$version' 不是安装器支持的数字版本格式（例如 0.1.0）。"
    }
    return $version
}

$installerScriptText = Get-Content -LiteralPath $installerScript -Raw
$appVersion = Get-ProjectVersion
if (($installerScriptText -match '(?m)^#define\s+MyAppVersion\s+"([^"]+)"') -and ($Matches[1] -ne $appVersion)) {
    throw "版本不一致：gpt2json.__version__=$appVersion，但 $installerScript 中 MyAppVersion=$($Matches[1])。请同步版本。"
}

$setupExe = Join-Path $root "release\GPT2JSON-Setup-v$appVersion.exe"
$source = Join-Path $root "packaging\windows\artsetup\ArtSetup.cs"
$out = Join-Path $root "release\GPT2JSON-ArtSetup-v$appVersion.exe"
$icon = Join-Path $root "gpt2json\assets\gpt2json_icon.ico"
$iconPng = Join-Path $root "gpt2json\assets\gpt2json_icon.png"
$shellArtPng = Join-Path $root "packaging\windows\assets\installer-art-shell-transparent.png"

$requiredFiles = @(
    @{ Path = $setupExe; Label = "Inno 安装核心；请先运行 build-installer.ps1" },
    @{ Path = $source; Label = "艺术安装器源码" },
    @{ Path = $icon; Label = "安装器图标 ICO" },
    @{ Path = $iconPng; Label = "安装器图标 PNG" },
    @{ Path = $shellArtPng; Label = "透明 Shell 艺术图" }
)
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file.Path)) { throw "缺少$($file.Label)：$($file.Path)" }
}

$cscCandidates = @(
    @(
        (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
    ) | Where-Object { Test-Path $_ }
)
if ($cscCandidates.Count -eq 0) { throw "未找到 .NET Framework C# 编译器 csc.exe。" }
$csc = [string]$cscCandidates[0]

$refRoot = "C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8"
if (-not (Test-Path $refRoot)) { $refRoot = "C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.7.2" }
if (-not (Test-Path $refRoot)) { throw "未找到 .NET Framework WPF 引用程序集目录。" }

$refs = @(
    (Join-Path $refRoot "PresentationCore.dll"),
    (Join-Path $refRoot "PresentationFramework.dll"),
    (Join-Path $refRoot "WindowsBase.dll"),
    (Join-Path $refRoot "System.Xaml.dll")
)
foreach ($r in $refs) { if (-not (Test-Path $r)) { throw "缺少引用程序集：$r" } }

New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent) | Out-Null
Write-Host "使用版本: $appVersion"
Write-Host "使用 C# 编译器: $csc"
Write-Host "输出艺术安装器: $out"

$generatedSourceDir = Join-Path ([System.IO.Path]::GetTempPath()) ("GPT2JSON-ArtSetup-Build-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $generatedSourceDir | Out-Null
$generatedSource = Join-Path $generatedSourceDir "ArtSetup.generated.cs"
$sourceText = Get-Content -LiteralPath $source -Raw
$sourceText = [regex]::Replace($sourceText, 'private\s+const\s+string\s+AppVersion\s+=\s+"[^"]*";', "private const string AppVersion = `"$appVersion`";")
if ($sourceText -notmatch [regex]::Escape("private const string AppVersion = `"$appVersion`";")) {
    throw "无法在艺术安装器源码中注入显示版本 v$appVersion。"
}
if ($sourceText -notmatch [regex]::Escape('"GPT2JSON-Setup-" + Version + ".exe"')) {
    throw "艺术安装器源码缺少按 Version 生成内嵌安装核心文件名的逻辑。"
}
Set-Content -LiteralPath $generatedSource -Value $sourceText -Encoding UTF8

$args = @(
    "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
    "/out:$out",
    "/win32icon:$icon",
    "/resource:$setupExe,GPT2JSON.Setup.exe",
    "/resource:$iconPng,GPT2JSON.Icon.png",
    "/resource:$shellArtPng,GPT2JSON.ShellArt.png"
)
foreach ($r in $refs) { $args += "/reference:$r" }
$args += $generatedSource

try {
    & $csc @args
    if ($LASTEXITCODE -ne 0) { throw "艺术安装器编译失败。" }
    Get-Item $out | Select-Object FullName, Length, LastWriteTime
}
finally {
    Remove-Item -LiteralPath $generatedSourceDir -Recurse -Force -ErrorAction SilentlyContinue
}
