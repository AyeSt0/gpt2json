#define MyAppName "GPT2JSON"
#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "GPT2JSON Contributors"
#define MyAppURL "https://github.com/AyeSt0/gpt2json"
#define MyAppExeName "GPT2JSON.exe"

[Setup]
AppId={{F3E03F2D-1CB1-4A63-98D1-0E19E1E20321}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Sub2API / CPA JSON 导出工具
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=GPT2JSON-Setup-v{#MyAppVersion}
SourceDir=..\..
SetupIconFile=gpt2json\assets\gpt2json_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardImageFile=packaging\windows\assets\installer-side.bmp
WizardSmallImageFile=packaging\windows\assets\installer-small.bmp
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
SetupLogging=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Messages]
chinesesimp.SetupAppTitle=安装
chinesesimp.SetupWindowTitle=安装 - %1
chinesesimp.UninstallAppTitle=卸载
chinesesimp.UninstallAppFullTitle=%1 卸载
chinesesimp.ConfirmTitle=确认
chinesesimp.ErrorTitle=错误
chinesesimp.ExitSetupTitle=退出安装
chinesesimp.ExitSetupMessage=安装尚未完成。如果现在退出，程序将不会被安装。%n%n你可以稍后再次运行安装程序继续安装。%n%n确定要退出安装吗？
chinesesimp.ButtonBack=< 上一步(&B)
chinesesimp.ButtonNext=下一步(&N) >
chinesesimp.ButtonInstall=安装(&I)
chinesesimp.ButtonOK=确定
chinesesimp.ButtonCancel=取消
chinesesimp.ButtonYes=是(&Y)
chinesesimp.ButtonNo=否(&N)
chinesesimp.ButtonFinish=完成(&F)
chinesesimp.ButtonBrowse=浏览(&B)...
chinesesimp.ButtonWizardBrowse=浏览(&B)...
chinesesimp.ButtonNewFolder=新建文件夹(&M)
chinesesimp.WelcomeLabel1=欢迎安装 [name]
chinesesimp.WelcomeLabel2=这将把 [name/ver] 安装到你的电脑。%n%n建议在继续之前关闭其他正在运行的应用程序。
chinesesimp.WizardSelectDir=选择安装位置
chinesesimp.SelectDirDesc=要把 [name] 安装到哪里？
chinesesimp.SelectDirLabel3=安装程序会将 [name] 安装到以下文件夹。
chinesesimp.SelectDirBrowseLabel=点击“下一步”继续；如需更换位置，请点击“浏览”。
chinesesimp.WizardSelectTasks=选择附加任务
chinesesimp.WizardReady=准备安装
chinesesimp.ReadyLabel1=安装程序已准备好开始安装 [name]。
chinesesimp.ReadyLabel2a=点击“安装”继续；如需检查或修改设置，请点击“上一步”。
chinesesimp.ReadyLabel2b=点击“安装”继续。
chinesesimp.WizardInstalling=正在安装
chinesesimp.InstallingLabel=正在安装 [name]，请稍候。
chinesesimp.FinishedHeadingLabel=正在完成 [name] 安装向导
chinesesimp.FinishedLabelNoIcons=[name] 已成功安装到你的电脑。
chinesesimp.FinishedLabel=[name] 已成功安装到你的电脑。你可以通过快捷方式启动它。
chinesesimp.ClickFinish=点击“完成”退出安装程序。
chinesesimp.RunEntryExec=启动 %1
chinesesimp.ConfirmUninstall=确定要完全移除 %1 及其所有组件吗？
chinesesimp.UninstallStatusLabel=正在从你的电脑移除 %1，请稍候。
chinesesimp.UninstalledAll=%1 已成功从你的电脑移除。

[CustomMessages]
chinesesimp.TaskDesktopIcon=创建桌面快捷方式
chinesesimp.RunAfterInstall=启动 GPT2JSON

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktopIcon}"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "dist\GPT2JSON\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "packaging\windows\build\GPT2JSON-ArtUninstall.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:RunAfterInstall}"; Flags: nowait postinstall skipifsilent

[Code]
function EnsureAppInstallDir(Value: String): String;
var
  Clean: String;
  Leaf: String;
begin
  Clean := RemoveBackslash(ExpandConstant(Value));
  Leaf := ExtractFileName(Clean);
  if CompareText(Leaf, '{#MyAppName}') = 0 then
    Result := Clean
  else
    Result := AddBackslash(Clean) + '{#MyAppName}';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = wpSelectDir then
    WizardForm.DirEdit.Text := EnsureAppInstallDir(WizardForm.DirEdit.Text);
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  WizardForm.DirEdit.Text := EnsureAppInstallDir(WizardDirValue);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  UninstallKey: String;
  ArtUninstaller: String;
  QuotedArtUninstaller: String;
begin
  if CurStep = ssPostInstall then
  begin
    UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{F3E03F2D-1CB1-4A63-98D1-0E19E1E20321}_is1';
    ArtUninstaller := ExpandConstant('{app}\GPT2JSON-ArtUninstall.exe');
    QuotedArtUninstaller := '"' + ArtUninstaller + '"';
    if FileExists(ArtUninstaller) then
    begin
      RegWriteStringValue(HKCU, UninstallKey, 'UninstallString', QuotedArtUninstaller);
      RegWriteStringValue(HKCU, UninstallKey, 'QuietUninstallString', QuotedArtUninstaller + ' /silent');
    end;
  end;
end;



