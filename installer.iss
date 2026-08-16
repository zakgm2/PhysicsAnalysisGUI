; installer.iss
; --------------
; Inno Setup script for PhysicsAnalysis. Requires Inno Setup 6
; (free, https://jrsoftware.org/isinfo.php) — install it, then either
; open this file in the Inno Setup Compiler GUI and click Compile, or
; run from a shell: iscc installer.iss
;
; Per-user install, no admin/UAC prompt ever (PrivilegesRequired=lowest)
; — required so the auto-updater (update_check.py) can silently install
; a new version with zero user interaction. Installs into a *versioned*
; subdirectory under %LOCALAPPDATA% (not a fixed path) so a future
; update never touches files the currently-running app has open — it
; just installs alongside into a new version folder and repoints the
; Start Menu shortcut.
;
; MUST update #define MyAppVersion below on every release, together with
; pyproject.toml and physicsanalysis_qt/__init__.py's __version__ — see
; Deployment Steps.md.

#define MyAppName "Physics Analysis GUI"
#define MyAppVersion "2.11.0"
#define MyAppPublisher "zakgm2"
#define MyAppExeName "PhysicsAnalysis.exe"

[Setup]
AppId={{B6E4B0B4-6B7B-4E4D-9B5B-9E7C9C6E3A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Versioned install dir - each release lands in its own folder, never
; overwriting a version that might still be running.
DefaultDirName={localappdata}\PhysicsAnalysis\app-{#MyAppVersion}
DisableProgramGroupPage=yes
; No admin rights, no UAC prompt - required for the silent auto-updater.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=PhysicsAnalysis-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=physicsanalysis_qt\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; The PyInstaller onedir build output - build this first (pyinstaller
; PhysicsAnalysis.spec) before compiling this installer.
Source: "dist\PhysicsAnalysis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; A stable Start Menu shortcut, always pointing at THIS release's
; versioned install dir - the updater repoints it to the new version's
; folder on every update rather than this shortcut itself moving.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
; No "skipifsilent" - this must still launch after a fully-silent
; auto-update install (the whole point of the auto-updater), not just
; after a manual interactive install.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall
