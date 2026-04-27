$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$setupExe = Join-Path $root "release\GPT2JSON-Setup-v0.1.0.exe"
$source = Join-Path $root "packaging\windows\artsetup\ArtSetup.cs"
$out = Join-Path $root "release\GPT2JSON-ArtSetup-v0.1.0.exe"
$icon = Join-Path $root "gpt2json\assets\gpt2json_icon.ico"
$iconPng = Join-Path $root "gpt2json\assets\gpt2json_icon.png"
$sidePng = Join-Path $root "packaging\windows\assets\installer-side-art-dark.png"

if (-not (Test-Path $setupExe)) { throw "未找到 Inno 安装核心：$setupExe。请先运行 build-installer.ps1。" }
if (-not (Test-Path $source)) { throw "未找到艺术安装器源码：$source" }

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
Write-Host "使用 C# 编译器: $csc"
Write-Host "输出艺术安装器: $out"

$args = @(
    "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
    "/out:$out",
    "/win32icon:$icon",
    "/resource:$setupExe,GPT2JSON.Setup.exe",
    "/resource:$iconPng,GPT2JSON.Icon.png",
    "/resource:$sidePng,GPT2JSON.Side.png"
)
foreach ($r in $refs) { $args += "/reference:$r" }
$args += $source

& $csc @args
if ($LASTEXITCODE -ne 0) { throw "艺术安装器编译失败。" }
Get-Item $out | Select-Object FullName, Length, LastWriteTime



