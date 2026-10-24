; Respected Orchestrator - per-user Windows installer (no administrator rights); works without the Hub.
; Built by packaging/build_installer.py. The installer owns the program files in {app}; the product's own commands own
; everything else: `setup` (install record, data folder), `repair`, `config`, `memory connect`, `uninstall` (docs/PRODUCT_CONTRACT.md).
; Shared with the Brain installer: the install-path page, the Hub download, the maintenance page, /SET= and /PURGE=1.
#ifndef AppVersion
  #define AppVersion "0.1.0b1"
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
AppVerName=Respected Orchestrator
UninstallDisplayName=Respected Orchestrator
AppVersion={#AppVersion}
AppPublisher=Respected
AppCopyright=Copyright (c) 2026 RESPECTED (MIT)
DefaultDirName={localappdata}\Respected\RespectedOrchestrator\app
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=RespectedOrchestrator-Windows-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\respected-orchestrator.exe
SetupIconFile=icon.ico
CloseApplications=yes
SetupLogging=yes
WizardStyle=modern
WizardImageFile=wizard\side-164x314.bmp,wizard\side-192x366.bmp,wizard\side-246x470.bmp,wizard\side-328x628.bmp
DisableWelcomePage=no
InfoAfterFile=UPDATE_NOTES.md
InfoBeforeFile=orchestrator_info.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Messages]
turkish.WizardInfoBefore=Bilgisayarında neler olur
turkish.InfoBeforeLabel=Kurulumda, kullanırken, güncellemede ve kaldırırken neler olacağını aşağıda okuyabilirsin.
turkish.WizardInfoAfter=Yenilikler
turkish.InfoAfterLabel=Bu sürümde neler değişti?
turkish.InfoAfterClickLabel=Devam etmek için Sonraki'ne tıklayın.
turkish.WelcomeLabel1=Respected Orchestrator'a hoş geldin
turkish.WelcomeLabel2=Orchestrator, ağır kodlama işlerini izole çalışma alanlarında yürütür; yamayı sen onaylamadan gerçek ağacına dokunmaz.%n%nYönetici izni gerekmez.%n%nDevam etmek için Sonraki'ne tıkla.
turkish.FinishedHeadingLabel=Respected Orchestrator hazır
turkish.FinishedLabel=Kurulum bitti.%n%nSon bir adım: kullandığın AI aracını yeniden başlat ve aracın ilgili yerinden (eklentiler, MCP) Orchestrator'a izin ver. Yoksa araç Orchestrator'ı görmez.
turkish.FinishedLabelNoIcons=Kurulum bitti.%n%nSon bir adım: kullandığın AI aracını yeniden başlat ve aracın ilgili yerinden (eklentiler, MCP) Orchestrator'a izin ver. Yoksa araç Orchestrator'ı görmez.
; the ready page's button is "Kur", not "Sonraki"
turkish.ReadyLabel2a=Kuruluma devam etmek için Kur düğmesine, ayarları gözden geçirmek ya da değiştirmek için Önceki düğmesine tıklayın.
turkish.ReadyLabel2b=Kuruluma başlamak için Kur düğmesine tıklayın.

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallRun]
; the product takes back its MCP registrations and removes its install record (and with /PURGE=1 or a yes its settings and runs)
Filename: "{app}\respected-orchestrator.exe"; Parameters: "{code:UninstallArgs}"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveProduct"

[InstallDelete]
; an update replaces the program folder whole: files of the previous version (old dist-info, renamed modules) must not stay behind
Type: filesandordirs; Name: "{app}\app"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
#include "respected_cards.iss"

const
  ProductName = 'Orchestrator';
  ProductExe = 'respected-orchestrator.exe';
  ProductFolder = 'RespectedOrchestrator';
  HubProductId = 'orchestrator';
  InstallRecord = 'app\.respected\install.json';  // the product's own install record, relative to its folder
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8E2B4D7A-61C3-4F09-A5D8-3B9E17C2F640}_is1';
  HubSetupName = 'RespectedHub-Setup.exe';  // local file name only; the release asset carries a version
  HubReleasesPage = 'https://github.com/respected0/respected-hub/releases';
  HubReleaseApi = 'https://api.github.com/repos/respected0/respected-hub/releases';
  Workers = 'codex,claude,gemini,antigravity,agy,cursor';

var
  ChoicePage, MaintenancePage, WorkerPage, MemoryPage: TWizardPage;
  DownloadPage: TDownloadWizardPage;
  Maintenance, SettingsMode, Leaving, PurgeData: Boolean;

{ ---- shared with the Brain installer ---- }

// /NAME=value command-line switches (silent installs, the Hub, tests)
function CommandValue(Name: String; Default: String): String;
var
  I: Integer;
  Prefix: String;
begin
  Result := Default;
  Prefix := '/' + Name + '=';
  for I := 1 to ParamCount do
    if CompareText(Copy(ParamStr(I), 1, Length(Prefix)), Prefix) = 0 then
      Result := Copy(ParamStr(I), Length(Prefix) + 1, MaxInt);
end;

// one ` --set "key=value"` argument; quotes are dropped so a value cannot end its own argument
function SetArg(Assignment: String): String;
begin
  StringChangeEx(Assignment, '"', '', True);
  Result := ' --set "' + Assignment + '"';
end;

// every /SET=key=value switch, as the product's own --set arguments
function SwitchSettings(): String;
var
  I: Integer;
begin
  Result := '';
  for I := 1 to ParamCount do
    if CompareText(Copy(ParamStr(I), 1, 5), '/SET=') = 0 then
      Result := Result + SetArg(Copy(ParamStr(I), 6, MaxInt));
end;

// --set arguments as `config set` arguments
function ConfigArgs(SetArgs: String): String;
begin
  Result := SetArgs;
  StringChangeEx(Result, ' --set ', ' ', True);
end;

function ProgramExe(): String;
begin
  Result := ExpandConstant('{localappdata}\Respected\' + ProductFolder + '\app\' + ProductExe);
end;

function DataRoot(): String;
begin
  Result := ExpandConstant('{localappdata}\Respected\' + ProductFolder + '\data');
end;

// installed = the program and the product's own install record are both there; anything less is a fresh install
function IsInstalled(): Boolean;
begin
  Result := FileExists(ProgramExe()) and FileExists(ExpandConstant('{localappdata}\Respected\' + ProductFolder + '\' + InstallRecord));
end;

function HubExe(): String;
begin
  Result := ExpandConstant('{localappdata}\Respected\RespectedHub\app\respected-hub.exe');
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

// the Hub installer is named after its version: take the Setup.exe asset of the newest Hub release
function HubDownloadUrl(): String;
var
  Json: AnsiString;
  Text: String;
  First, Last: Integer;
begin
  Result := CommandValue('HUBURL', '');
  if Result <> '' then Exit;
  DownloadTemporaryFile(HubReleaseApi, 'hub-latest.json', '', @OnDownloadProgress);
  LoadStringFromFile(ExpandConstant('{tmp}\hub-latest.json'), Json);
  Text := String(Json);
  Last := Pos('-Windows-x64-Setup.exe"', Text);
  if Last = 0 then RaiseException('Hub kurucusu sürüm listesinde yok');
  Last := Last + 21;
  First := Last;
  while (First > 1) and (Text[First - 1] <> '"') do First := First - 1;
  Result := Copy(Text, First, Last - First + 1);
end;

function FetchHubSetup(): Boolean;
begin
  Result := False;
  try
    if WizardSilent then
      DownloadTemporaryFile(HubDownloadUrl(), HubSetupName, '', @OnDownloadProgress)
    else begin
      DownloadPage.Clear;
      DownloadPage.Add(HubDownloadUrl(), HubSetupName, '');
      DownloadPage.Show;
      try
        DownloadPage.Download;
      finally
        DownloadPage.Hide;
      end;
    end;
    Result := True;
  except
    Log('Hub indirilemedi: ' + GetExceptionMessage);
  end;
end;

// get the newest Hub when it is missing, install it, then open it on this product's install page
procedure ContinueWithHub;
var
  Code: Integer;
begin
  if not FileExists(HubExe()) then
    if FetchHubSetup() then
      Exec(ExpandConstant('{tmp}\' + HubSetupName), '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_SHOWNORMAL, ewWaitUntilTerminated, Code);
  if FileExists(HubExe()) then
    Exec(HubExe(), '--install=' + HubProductId, '', SW_SHOWNORMAL, ewNoWait, Code)
  else if not WizardSilent then begin
    ShellExec('open', HubReleasesPage, '', '', SW_SHOWNORMAL, ewNoWait, Code);
    MsgBox('Respected Hub indirilip kurulamadı. Açılan sayfadan Hub kurucusunu (Setup.exe) indirip çalıştır; Hub, ' + ProductName + ' ürününü senin için kuracak.', mbInformation, MB_OK);
  end;
end;

// runs one of the product's own commands; Output gets its standard output lines
function RunProduct(Params: String; var Output: TExecOutput): Boolean;
var
  Code, I: Integer;
begin
  Result := ExecAndCaptureOutput(ProgramExe(), Params, '', SW_HIDE, ewWaitUntilTerminated, Code, Output) and (Code = 0);
  if not Result then begin
    Log(ProductExe + ' ' + Params + ' failed with exit code ' + IntToStr(Code));
    // the product explains the refusal on stdout (JSON conflicts) or stderr; without it the setup log names no cause
    for I := 0 to GetArrayLength(Output.StdOut) - 1 do Log('  stdout: ' + Output.StdOut[I]);
    for I := 0 to GetArrayLength(Output.StdErr) - 1 do Log('  stderr: ' + Output.StdErr[I]);
  end;
end;

// the value of `config get <key>`, whose output is {"<key>": <value>} (one line or one member per line)
function CurrentSetting(Key: String): String;
var
  Output: TExecOutput;
  I, P: Integer;
begin
  Result := '';
  if not RunProduct('config get ' + Key, Output) then Exit;
  for I := 0 to GetArrayLength(Output.StdOut) - 1 do begin
    P := Pos('": ', Output.StdOut[I]);
    if P > 0 then begin
      Result := Trim(Copy(Output.StdOut[I], P + 3, MaxInt));
      if (Result <> '') and (Result[Length(Result)] = '}') then Result := Trim(Copy(Result, 1, Length(Result) - 1)); // one-line output
      if (Length(Result) >= 2) and (Result[1] = '"') then begin
        Result := Copy(Result, 2, Length(Result) - 2);
        StringChangeEx(Result, '\"', '"', True);
        StringChangeEx(Result, '\\', '\', True);
      end;
    end;
  end;
end;

// the AI tools keep our MCP server and hooks running from the program folder, and Restart Manager cannot close them:
// stop exactly the processes of this product's program (matched by full path), so an update or removal while they are open works
procedure StopRunningProduct;
var
  Code: Integer;
  AppDir: String;
begin
  AppDir := ExpandConstant('{app}');
  if not FileExists(AppDir + '' + ProductExe) then Exit;  // a first install has nothing to stop: skip PowerShell and the wait (~1.5 s)
  StringChangeEx(AppDir, '''', '''''', True);
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq ''' + ProductExe +
    ''' -and $_.ExecutablePath -like ''' + AppDir + '\*'' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
    '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(700);
end;

{ ---- update safety net (shared with the Orchestrator installer) ----
  Before an update replaces the program, the installer keeps the previous program folder and the data root's top-level
  *.json files (the only files a format migration touches) under update-backup. When `repair` fails, or the product was
  healthy before the update and is not afterwards, both are put back and the update is reported as failed; otherwise
  the backup is deleted. The person's vault and the AI tools' files are never part of it (the product's own transaction
  already undoes those). Without a backup the update does not start. }
var
  UpdateBackedUp, HealthyBefore: Boolean;
  PreviousVersion: String;

function UpdateBackup(): String;
begin
  Result := ExpandConstant('{localappdata}\Respected\' + ProductFolder + '\update-backup');
end;

function Robocopy(Arguments: String): Boolean;
var
  Code: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\robocopy.exe'), Arguments + ' /NFL /NDL /NJH /NJS /NP /R:2 /W:1', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code < 8);
  if not Result then Log('robocopy ' + Arguments + ' failed with exit code ' + IntToStr(Code));
end;

function BackUpForUpdate(): Boolean;
var
  Output: TExecOutput;
begin
  Result := True;
  UpdateBackedUp := False;
  if not Maintenance then Exit;
  DelTree(UpdateBackup(), True, True, True);
  HealthyBefore := RunProduct('health', Output);
  if not RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', PreviousVersion) then PreviousVersion := '';
  UpdateBackedUp := Robocopy('"' + ExpandConstant('{app}') + '" "' + UpdateBackup() + '\program" /MIR')
    and Robocopy('"' + DataRoot() + '" "' + UpdateBackup() + '\data" *.json');
  Result := UpdateBackedUp;
end;

procedure CommitUpdate;
begin
  if UpdateBackedUp then DelTree(UpdateBackup(), True, True, True);
  UpdateBackedUp := False;
end;

// puts the previous program and data files back and ends the update as failed (never returns)
procedure RollBackUpdate(Reason: String);
var
  Restored: Boolean;
begin
  StopRunningProduct;
  Restored := Robocopy('"' + UpdateBackup() + '\program" "' + ExpandConstant('{app}') + '" /MIR')
    and Robocopy('"' + UpdateBackup() + '\data" "' + DataRoot() + '" *.json /IS /IT');
  if not Restored then
    RaiseException(ProductName + ' ' + Reason + ' Önceki sürüm geri yüklenemedi; kopyası şurada duruyor: ' + UpdateBackup());
  if PreviousVersion <> '' then RegWriteStringValue(HKCU, UninstallKey, 'DisplayVersion', PreviousVersion);
  CommitUpdate;
  Log(ProductName + ' ' + Reason + ' Önceki sürüm geri yüklendi.');
  SuppressibleMsgBox(ProductName + ' ' + Reason + #13#10 + 'Önceki sürüm geri yüklendi; ayarlarınız ve verileriniz değişmedi.', mbError, MB_OK, IDOK);
  Abort;  // a non-zero exit code, so a script or the Hub sees that the update did not happen
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  StopRunningProduct;
  if not BackUpForUpdate() then
    Result := ProductName + ' güncellenmeden önce yedeği alınamadı (disk dolu ya da dosyalar kullanımda olabilir); hiçbir şey değiştirilmedi.';
end;

// unattended through the Hub: `Setup.exe /VERYSILENT /HUB=1`
function InitializeSetup(): Boolean;
begin
  Result := True;
  if WizardSilent and (CommandValue('HUB', '') <> '') then begin
    ContinueWithHub;
    Result := False;
  end;
end;

function UninstallerPath(): String;
begin
  Result := '';
  if RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', Result) then Result := RemoveQuotes(Result);
end;

procedure CreateSharedPages;
begin
  ChoicePage := NewCardPage(0, wpWelcome, 'Kurulum yolu', 'İkisi de aynı ürünü kurar; fark, güncellemeleri ve ayarları nereden yöneteceğindir.', False);
  AddCard(ChoicePage, 0, #$E80F, 'Respected Hub ile devam et (önerilen)', 'Kurulum, güncelleme ve ayarlar görsel arayüzden yönetilir.', True);
  AddCard(ChoicePage, 0, #$E756, 'Yalnızca ' + ProductName, 'Hub olmadan; ayarlar bu kurucudan ya da komutlarla değiştirilir.', False);
  MaintenancePage := NewCardPage(1, ChoicePage.ID, ProductName + ' kurulu', 'Ayarların ve not kasan her seçenekte korunur.', False);
  AddCard(MaintenancePage, 1, #$E895, 'Onar / Güncelle', 'Programı bu kurucudaki sürümle (v{#AppVersion}) yeniler.', True);
  AddCard(MaintenancePage, 1, #$E713, 'Ayarları değiştir', 'Programa dokunmadan ayarları yeniden seçersin.', False);
  AddCard(MaintenancePage, 1, #$E74D, 'Kaldır', 'Programı kaldırır; sana sorarak ayarları ve verileri de siler.', False);
  DownloadPage := CreateDownloadPage('Hub indiriliyor', 'En güncel Respected Hub kurucusu indiriliyor...', @OnDownloadProgress);
end;

{ ---- Orchestrator's own questions ---- }

function WorkerName(Index: Integer): String;
var
  Rest: String;
  I, P: Integer;
begin
  Rest := Workers + ',';
  for I := 0 to Index - 1 do Delete(Rest, 1, Pos(',', Rest));
  P := Pos(',', Rest);
  Result := Copy(Rest, 1, P - 1);
end;

function BrainInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Respected\RespectedBrain\app\respected-brain.exe'));
end;

procedure InitializeWizard;
var
  I: Integer;
begin
  TidyInfoPages;
  Maintenance := IsInstalled();
  CreateSharedPages;
  WorkerPage := NewCardPage(3, MaintenancePage.ID, 'Varsayılan çalışan', 'Hangi AI aracı görev yapsın? Araç bu bilgisayarda kurulu olmalı.', False);
  CompactCards(3);
  for I := 0 to 5 do AddCard(WorkerPage, 3, #$E756, WorkerName(I), '', I = 0);
  MemoryPage := NewCardPage(2, WorkerPage.ID, 'Brain hafızası', 'Orchestrator Brain hafızanı kullanabilsin mi? Sonradan kapatılabilir.', True);
  AddCard(MemoryPage, 2, #$E8F1, 'Brain hafızasını oku', 'Görevler, Brain kasandaki notlardan kısa özetler okur. Brain kurulu olmalı.', False);
  AddCard(MemoryPage, 2, #$E70F, 'Gelen kutusuna not yazabilsin', 'Yeniden kullanılabilir notlar Brain gelen kutusuna bırakılır.', False);
end;

// the page answers as the product's own `config set` arguments
function PageSettings(): String;
begin
  Result := ' "default_worker=' + WorkerName(CardSelectedIndex(3)) + '"';
end;

procedure LoadCurrentSettings;
var
  I: Integer;
  Current: String;
begin
  Current := CurrentSetting('default_worker');
  for I := 0 to 5 do
    if WorkerName(I) = Current then SetCardChecked(3, I, True);
  SetCardChecked(2, 0, CurrentSetting('memory_enabled') = 'true');
  SetCardChecked(2, 1, CurrentSetting('memory_write') = 'true');
end;

// connect or disconnect the Brain memory as the page says; failures are reported, never fatal
procedure ApplyMemoryChoice;
var
  Output: TExecOutput;
begin
  if CardChecked(2, 0) and BrainInstalled() then begin
    if CardChecked(2, 1) then RunProduct('memory connect --write', Output) else RunProduct('memory connect', Output);
  end else if SettingsMode then
    RunProduct('memory disconnect', Output);
end;

{ ---- page flow ---- }

procedure ProductPageChanged(CurPageID: Integer);
begin
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = ChoicePage.ID then Result := WizardSilent or Maintenance
  else if PageID = MaintenancePage.ID then Result := WizardSilent or not Maintenance
  else if (PageID = WorkerPage.ID) or (PageID = MemoryPage.ID) then Result := Maintenance and not SettingsMode
  else if PageID = wpInfoAfter then Result := not Maintenance;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if Leaving then Confirm := False;
end;

procedure Leave;
begin
  Leaving := True;
  WizardForm.Close;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Output: TExecOutput;
  Code: Integer;
begin
  Result := True;
  if WizardSilent then Exit;
  if (CurPageID = ChoicePage.ID) and (CardSelectedIndex(0) = 0) then begin
    ContinueWithHub;
    Result := False;
    Leave;
  end else if (CurPageID = MaintenancePage.ID) and (CardSelectedIndex(1) = 1) then begin
    SettingsMode := True;
    LoadCurrentSettings;
  end else if (CurPageID = MaintenancePage.ID) and (CardSelectedIndex(1) = 2) then begin
    Exec(UninstallerPath(), '', '', SW_SHOWNORMAL, ewNoWait, Code);
    Result := False;
    Leave;
  end else if (CurPageID = MemoryPage.ID) and SettingsMode then begin
    // settings only: the product applies them itself; the program files are not touched
    if RunProduct('config set' + PageSettings(), Output) then begin
      ApplyMemoryChoice;
      MsgBox('Ayarlar kaydedildi.', mbInformation, MB_OK);
    end else
      MsgBox('Ayarlar kaydedilemedi; hiçbir şey değişmedi. Ayrıntı için: respected-orchestrator config', mbError, MB_OK);
    Result := False;
    Leave;
  end;
end;

// ends a failed install or repair: the message, then Abort (non-zero exit code); the cards' finish page then says it failed
procedure FailInstall(Message: String);
begin
  InstallFailed := True;
  SuppressibleMsgBox(Message, mbError, MB_OK, IDOK);
  Abort;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Output: TExecOutput;
begin
  if CurStep <> ssPostInstall then Exit;
  // over an installed product the program files were just replaced: the product re-verifies them and rewrites its record
  if Maintenance then begin
    if not RunProduct('repair', Output) then begin
      if UpdateBackedUp then RollBackUpdate('onarılamadı.');
      FailInstall(ProductName + ' onarılamadı; kurucuyu yeniden çalıştırabilirsin.');
    end;
    if UpdateBackedUp and HealthyBefore and not RunProduct('health', Output) then RollBackUpdate('güncellemeden sonra sağlıklı çalışmadı.');
    CommitUpdate;
  end else begin
    if not RunProduct('setup', Output) then
      FailInstall(ProductName + ' kurulumu tamamlanamadı; kurucuyu yeniden çalıştırabilirsin.');
    if not WizardSilent then begin
      RunProduct('config set' + PageSettings(), Output);
      ApplyMemoryChoice;
    end;
  end;
  if SwitchSettings() <> '' then
    if not RunProduct('config set' + ConfigArgs(SwitchSettings()), Output) then
      RaiseException(ProductName + ' kuruldu ama /SET ayarları uygulanamadı.');
end;

{ ---- removal ---- }

// interactive removal asks about settings and data (the vault never goes); silent removal keeps them unless /PURGE=1
function InitializeUninstall(): Boolean;
begin
  Result := True;
  StopRunningProduct;
  PurgeData := CommandValue('PURGE', '') <> '';
  if not UninstallSilent then
    PurgeData := MsgBox('Ayarlar ve görev çalışma kayıtları da silinsin mi?' + #13#10 + '(Hayır dersen yeniden kurduğunda kaldığın yerden devam edersin.)', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

function UninstallArgs(Param: String): String;
begin
  if PurgeData then Result := 'uninstall --purge' else Result := 'uninstall';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then Exit;
  if PurgeData then DelTree(DataRoot(), True, True, True);
  RemoveDir(ExpandConstant('{localappdata}\Respected\' + ProductFolder));
  RemoveDir(ExpandConstant('{localappdata}\Respected'));
end;
