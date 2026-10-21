; Respected Orchestrator - per-user Windows installer (no administrator rights); works without the Hub.
; Built by packaging/build_installer.py, which stages the packaged distribution (respected-orchestrator.exe, app/, distribution.json).
; The installer copies the folder; the program's own `setup` / `uninstall` commands write and remove its install record.
#ifndef AppVersion
  #define AppVersion "0.1.0-beta.1"
#endif
#ifndef StageDir
  #define StageDir "..\..\dist\RespectedOrchestrator"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{8E2B4D7A-61C3-4F09-A5D8-3B9E17C2F640}
AppName=Respected Orchestrator
AppVersion={#AppVersion}
AppPublisher=Respected
DefaultDirName={localappdata}\Respected\RespectedOrchestrator\app
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=RespectedOrchestrator-Windows-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\respected-orchestrator.exe
CloseApplications=yes
WizardStyle=modern

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
; record the install next to the program (RPP lifecycle record, the same one `update` and `repair` re-verify)
Filename: "{app}\respected-orchestrator.exe"; Parameters: "setup"; Flags: runhidden waituntilterminated; StatusMsg: "Kurulum kaydı yazılıyor..."

[UninstallRun]
; removes only the install record; task runs and settings in the data folder are kept (uninstall --purge is a separate, explicit command)
Filename: "{app}\respected-orchestrator.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RecordRemove"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.respected"
