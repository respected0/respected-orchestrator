; Respected Orchestrator - per-user Windows installer (no administrator rights); stands alone.
; Built by packaging/build_installer.py. This script only lays the program files down in {app} and takes them away again (ADR-031).
; Everything else is the product's own: the first start of the engine records the verified build (`setup`), and `config`,
; `integrations`, `memory connect`, `repair` and `uninstall` (before the program is removed) are run by the desktop app or the person.
#ifndef AppVersion
  #define AppVersion "0.1.0b4"
#endif
#ifndef StageDir
  #define StageDir "..\..\dist\RespectedOrchestrator"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#ifndef AppIdValue
  #define AppIdValue "{{8E2B4D7A-61C3-4F09-A5D8-3B9E17C2F640}"
#endif

[Setup]
AppId={#AppIdValue}
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
UninstallDisplayIcon={app}\rorch.exe
SetupIconFile=icon.ico
; Windows closes whatever still holds a file this script replaces (the desktop app, the engine, an AI tool's MCP server) before it copies
CloseApplications=force
RestartApplications=no
SetupLogging=yes
WizardStyle=modern
WizardImageFile=wizard\side-164x314.bmp,wizard\side-192x366.bmp,wizard\side-246x470.bmp,wizard\side-328x628.bmp
DisableWelcomePage=no
InfoAfterFile=UPDATE_NOTES.md
InfoBeforeFile=orchestrator_info.txt

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Messages]
turkish.WizardInfoBefore=Bilgisayarınızda neler olur
turkish.InfoBeforeLabel=Kurulumda, kullanırken, güncellemede ve kaldırırken neler olacağını aşağıda okuyabilirsiniz.
turkish.WizardInfoAfter=Yenilikler
turkish.InfoAfterLabel=Bu sürümde neler değişti?
turkish.InfoAfterClickLabel=Devam etmek için Sonraki'ne tıklayın.
turkish.WelcomeLabel1=Respected Orchestrator'a hoş geldiniz
turkish.WelcomeLabel2=Orchestrator, kodlama ajanlarını çalıştırır ve işin gerçekten bittiğini kanıtlar; yamayı siz onaylamadan gerçek ağacınıza dokunmaz.%n%nYönetici izni gerekmez. Bu kurucu yalnızca program dosyalarını yerleştirir; ayarlar ve bağlantılar uygulamanın kendisinden yapılır.%n%nDevam etmek için Sonraki'ne tıklayın.
turkish.FinishedHeadingLabel=Respected Orchestrator hazır
turkish.FinishedLabel=Dosyalar yerleştirildi.%n%nMasaüstü uygulamasını açın; ilk açılışta kurulumu kendisi tamamlar. AI araçlarına bağlamak için uygulamanın Bağlantılar bölümünü ya da `rorch integrations` komutunu kullanın.
turkish.FinishedLabelNoIcons=Dosyalar yerleştirildi.%n%nKurulumu `rorch setup` ile tamamlayabilirsiniz; AI araçlarına bağlamak için `rorch integrations` komutunu kullanın.
turkish.ReadyLabel2a=Kuruluma devam etmek için Kur düğmesine tıklayın.
turkish.ReadyLabel2b=Kuruluma başlamak için Kur düğmesine tıklayın.

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ADR-025: the desktop shell sits next to the engine launcher. A Start menu entry exists only when this build ships it.
#ifexist StageDir + "\respected-orchestrator-desktop.exe"
[Icons]
Name: "{autoprograms}\Respected Orchestrator"; Filename: "{app}\respected-orchestrator-desktop.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Respected Orchestrator"; Filename: "{app}\respected-orchestrator-desktop.exe"; WorkingDir: "{app}"
#endif

[InstallDelete]
; an update replaces the program folder whole: files of the previous version (old dist-info, renamed modules) must not stay behind
Type: filesandordirs; Name: "{app}\app"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
