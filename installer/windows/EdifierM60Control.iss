#ifndef MyAppVersion
  #define MyAppVersion "1.2.0"
#endif

[Setup]
AppId={{8D6D7A38-6A2F-4E9C-A7F1-5B90A7D30600}
AppName=Edifier M60 / M90 Studio Control
AppVersion={#MyAppVersion}
AppPublisher=Droid567492 (Community / AI-Assisted)
AppPublisherURL=https://github.com/Droid567492/EdifierDesktop
AppSupportURL=https://github.com/Droid567492/EdifierDesktop/issues
AppUpdatesURL=https://github.com/Droid567492/EdifierDesktop/releases
DefaultDirName={autopf}\EdifierM60Control
DefaultGroupName=Edifier M60 / M90 Studio Control
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=EdifierM60Control-v{#MyAppVersion}-win64-setup
SetupIconFile=..\..\build\app.ico
UninstallDisplayIcon={app}\EdifierM60Control.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start with Windows (quietly in the system tray)"; GroupDescription: "Startup:"

[Files]
Source: "..\..\dist\EdifierM60Control.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Edifier M60 / M90 Studio Control"; Filename: "{app}\EdifierM60Control.exe"
Name: "{group}\Uninstall Edifier M60 / M90 Studio Control"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Edifier M60 / M90 Studio Control"; Filename: "{app}\EdifierM60Control.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EdifierM60Control"; ValueData: """{app}\EdifierM60Control.exe"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\EdifierM60Control.exe"; Description: "{cm:LaunchProgram,Edifier M60 / M90 Studio Control}"; Flags: nowait postinstall skipifsilent
