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

[Code]
var
  ChoicePage: TInputOptionWizardPage;
  HubChosen: Boolean;

function HubExe(): String;
begin
  Result := ExpandConstant('{localappdata}\Respected\RespectedHub\app\respected-hub.exe');
end;

function AlreadyInstalled(): Boolean;
begin
  Result := RegValueExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8E2B4D7A-61C3-4F09-A5D8-3B9E17C2F640}_is1', 'UninstallString');
end;

// Two ways to the same installed product: through the Hub (recommended) or on its own. Silent installs and updates skip the question.
procedure CreateChoicePage;
begin
  ChoicePage := CreateInputOptionPage(wpWelcome, 'Kurulum yolu', 'Nasıl devam etmek istersin?',
    'İkisi de aynı ürünü kurar; fark, güncellemeleri ve ayarları nereden yöneteceğindir.', True, False);
  ChoicePage.Add('Respected Hub ile devam et (önerilen): kurulum, güncelleme ve ayarlar görsel arayüzden yönetilir');
  ChoicePage.Add('Yalnızca Orchestrator (gelişmiş / geliştiriciler için): Hub olmadan, bu kurucuyla');
  ChoicePage.SelectedValueIndex := 0;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = ChoicePage.ID) and (WizardSilent or AlreadyInstalled());
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if HubChosen then Confirm := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Code: Integer;
begin
  Result := True;
  if WizardSilent or (CurPageID <> ChoicePage.ID) or (ChoicePage.SelectedValueIndex <> 0) then Exit;
  if FileExists(HubExe()) then
    Exec(HubExe(), '--install=orchestrator', '', SW_SHOWNORMAL, ewNoWait, Code)
  else begin
    ShellExec('open', 'https://github.com/respected0/respected-hub/releases/latest', '', '', SW_SHOWNORMAL, ewNoWait, Code);
    MsgBox('Respected Hub kurulu değil. Açılan sayfadan RespectedHub-Windows-Setup.exe dosyasını indirip çalıştırın; Hub, Orchestrator ürününü senin için kuracak.', mbInformation, MB_OK);
  end;
  HubChosen := True;
  Result := False;
  WizardForm.Close;
end;

procedure InitializeWizard;
begin
  CreateChoicePage;
end;

[Run]
; record the install next to the program (RPP lifecycle record, the same one `update` and `repair` re-verify)
Filename: "{app}\respected-orchestrator.exe"; Parameters: "setup"; Flags: runhidden waituntilterminated; StatusMsg: "Kurulum kaydı yazılıyor..."

[UninstallRun]
; removes only the install record; task runs and settings in the data folder are kept (uninstall --purge is a separate, explicit command)
Filename: "{app}\respected-orchestrator.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RecordRemove"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.respected"
