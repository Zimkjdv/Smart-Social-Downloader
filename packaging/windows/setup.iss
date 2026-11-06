#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef BuildVersion
  #define BuildVersion "0.1.0"
#endif
#ifndef ProductId
  #define ProductId "{{AE00B52D-658B-493E-A599-A9B077D54652}"
#endif
[Setup]
AppId={#ProductId}
AppName=Smart Social Downloader
AppVersion={#BuildVersion}
AppPublisher=Smart Social Downloader contributors
AppPublisherURL=https://github.com/Zimkjdv/Smart-Social-Downloader
DefaultDirName={localappdata}\Programs\Smart Social Downloader
DefaultGroupName=Smart Social Downloader
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
LicenseFile={#BundleDir}\_internal\licenses\PROJECT-LICENSE.txt
OutputBaseFilename=SmartSocialDownloader-{#BuildVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
AppMutex=Local\SSDL.InstalledApplication
SetupMutex=Local\SSDL.Installation.Active
UninstallDisplayIcon={app}\SmartSocialDownloader.exe
UninstallLogMode=append
DisableProgramGroupPage=yes
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑 / Create desktop shortcut"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "{#BundleDir}\_internal\tools-runtime\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\Smart Social Downloader"; Filename: "{app}\SmartSocialDownloader.exe"
Name: "{group}\匯入舊版資料"; Filename: "{app}\SmartSocialDownloader.exe"; Parameters: "--role migrate"
Name: "{group}\回復匯入前資料"; Filename: "{app}\SmartSocialDownloader.exe"; Parameters: "--role rollback"
Name: "{group}\停止背景服務"; Filename: "{app}\ssdl-runtime.exe"; Parameters: "--role control stop"; Flags: runminimized
Name: "{autodesktop}\Smart Social Downloader"; Filename: "{app}\SmartSocialDownloader.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SmartSocialDownloader.exe"; Description: "開啟 Smart Social Downloader"; Flags: nowait postinstall skipifsilent

; No user data/cache/media paths appear in Files/UninstallDelete. Uninstall keeps them.

[Code]
function HasWebView2: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := RegQueryStringValue(HKCU, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
  if not Result then
    Result := RegQueryStringValue(HKLM32, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Result := '';
  if HasWebView2 then Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then
  begin
    Result := 'Cannot start Microsoft WebView2 Setup. Install WebView2 Runtime and retry.';
    Exit;
  end;
  if Code = 3010 then NeedsRestart := True;
  if ((Code <> 0) and (Code <> 3010)) or not HasWebView2 then
    Result := 'WebView2 Runtime is required. Connect to the Internet, install or repair Microsoft WebView2 Runtime, and retry.';
end;
