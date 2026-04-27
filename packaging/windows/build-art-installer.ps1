$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$installerScript = Join-Path $root "packaging\windows\GPT2JSON.iss"
if (-not (Test-Path $installerScript)) { throw "未找到 Inno Setup 脚本：$installerScript" }

$installerScriptText = Get-Content -LiteralPath $installerScript -Raw
if ($installerScriptText -notmatch '(?m)^#define\s+MyAppVersion\s+"([^"]+)"') {
    throw "无法从 Inno Setup 脚本读取 MyAppVersion：$installerScript"
}
$appVersion = $Matches[1]

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

$args = @(
    "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
    "/out:$out",
    "/win32icon:$icon",
    "/resource:$setupExe,GPT2JSON.Setup.exe",
    "/resource:$iconPng,GPT2JSON.Icon.png",
    "/resource:$shellArtPng,GPT2JSON.ShellArt.png"
)
foreach ($r in $refs) { $args += "/reference:$r" }
$args += $source

& $csc @args
if ($LASTEXITCODE -ne 0) { throw "艺术安装器编译失败。" }
Get-Item $out | Select-Object FullName, Length, LastWriteTime
