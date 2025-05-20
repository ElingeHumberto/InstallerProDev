#define MyAppVersion "1.0.0"
#define MyAppName    "InstallerPro"

[Setup]
AppId={{DE6F4DAE-538C-4D14-BE74-2D98F3ACB1E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
WizardStyle=modern
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppName}.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename={#MyAppName}Setup_{#MyAppVersion}
SetupIconFile=icons\installerpro.ico

[Files]
Source:"dist\InstallerPro.exe"; DestDir:"{app}"; Flags:ignoreversion

[Icons]
Name:"{group}\{#MyAppName}"; Filename:"{app}\{#MyAppName}.exe"
Name:"{commondesktop}\{#MyAppName}"; Filename:"{app}\{#MyAppName}.exe"; Tasks:desktopicon

[Tasks]
Name:desktopicon; Description:"Crear icono en el Escritorio"; Flags:unchecked
