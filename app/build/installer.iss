; Inno Setup Script für StoneBook V3
#define MyAppName "StoneBook"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "G4MEOVER"
#define MyAppExeName "StoneBook.exe"

[Setup]
AppId={{8B1F2C30-5A4E-4D7B-9C2E-STONEBOOKV3}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\StoneBook
DefaultGroupName=StoneBook
DisableProgramGroupPage=yes
OutputBaseFilename=StoneBook_V3_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\StoneBook\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\StoneBook"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\StoneBook"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,StoneBook}"; Flags: nowait postinstall skipifsilent
