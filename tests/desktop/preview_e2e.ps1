# B3-06.03 real-window test: the built desktop app, the packaged engine, a hostile page on loopback, driven through UI Automation.
# Usage: powershell -File preview_e2e.ps1 -App <respected-orchestrator-desktop.exe> -Engine <dist\RespectedOrchestrator> -Enabled 1|0 -Url <address> [-Port 47731]
param([string]$App, [string]$Engine, [int]$Enabled = 1, [string]$Url = "", [int]$Port = 47731, [string]$Out = "$env:TEMP\preview-e2e")
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
New-Item -ItemType Directory -Force $Out | Out-Null
$log = Join-Path $Out "server.log"; Remove-Item $log -ErrorAction SilentlyContinue
$data = Join-Path $Out "data"; Remove-Item $data -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $data | Out-Null
$settings = @{ preview_enabled = [bool]$Enabled; preview_ports = "$Port" } | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $data "settings.json"), $settings)
if ($Url -eq "") { $Url = "http://127.0.0.1:$Port/" }

$server = Start-Process python -ArgumentList @((Join-Path $PSScriptRoot "preview_hostile_server.py"), $Port, $log) -PassThru -WindowStyle Hidden
Start-Sleep 1
$env:RESPECTED_APP_DIR = $Engine; $env:RESPECTED_DATA_DIR = $data
$proc = Start-Process $App -PassThru
$result = [ordered]@{ enabled = $Enabled; url = $Url }
try {
  $root = [Windows.Automation.AutomationElement]::RootElement
  $deadline = (Get-Date).AddSeconds(40); $main = $null
  while (-not $main -and (Get-Date) -lt $deadline) {
    $cond = New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::ProcessIdProperty), $proc.Id
    $main = $root.FindFirst('Children', $cond); if (-not $main) { Start-Sleep -Milliseconds 500 }
  }
  if (-not $main) { throw "main window not found" }
  function Find($scope, $name, $type = $null, $seconds = 25) {
    $end = (Get-Date).AddSeconds($seconds)
    do {
      $c = New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::NameProperty), $name
      $e = $scope.FindFirst('Descendants', $c)
      if ($e) { return $e }
      Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $end)
    return $null
  }
  $link = Find $main "Ayarlar"
  if (-not $link) { throw "Ayarlar link not found" }
  $link.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
  $box = Find $main "Önizleme adresi"
  if (-not $box) {
    $seen = $main.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition) | ForEach-Object { $_.Current.ControlType.ProgrammaticName + ':' + $_.Current.Name } | Where-Object { $_ -notmatch ':$' } | Select-Object -Unique -First 60
    throw ("address box not found; visible: " + ($seen -join ' | '))
  }
  $box.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($Url)
  $button = Find $main "Önizlemeyi aç"
  $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
  Start-Sleep -Seconds 1
  # what did the shell answer?
  $alert = $null
  foreach ($i in 1..10) {
    $texts = $main.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition) | ForEach-Object { $_.Current.Name } | Where-Object { $_ -match "^(Yerel önizleme kapalı|\d+ portu izin listesinde|Yalnızca http|Yalnızca 127|Adres geçersiz|Açıldı:|Adreste|Önizleme açık ama|pencere açılamadı)" }
    if ($texts) { $alert = ($texts | Select-Object -First 1); break }
    Start-Sleep -Milliseconds 500
  }
  $result.shell_answer = $alert
  if ($Enabled -eq 1 -and $alert -like "Açıldı:*") { Start-Sleep -Seconds 8 }  # let the hostile page run and report
  $windows = $root.FindAll('Children', (New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::ProcessIdProperty), $proc.Id)) | ForEach-Object { $_.Current.Name }
  $result.windows = @($windows)
  $previewTexts = @()
  foreach ($w in $root.FindAll('Children', (New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::ProcessIdProperty), $proc.Id))) {
    if ($w.Current.Name -like "Önizleme*") {
      $previewTexts = @($w.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition) | ForEach-Object { $_.Current.Name } | Where-Object { $_ } | Select-Object -Unique -First 12)
    }
  }
  $result.preview_window_texts = $previewTexts
} finally {
  if ($proc -and -not $proc.HasExited) { Stop-Process $proc -Force }
  Get-Process respected-orchestrator -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Engine*" } | Stop-Process -Force
  if ($server) { Stop-Process $server -Force }
  Remove-Item Env:RESPECTED_APP_DIR, Env:RESPECTED_DATA_DIR -ErrorAction SilentlyContinue
}
$result.server_log = if (Test-Path $log) { @(Get-Content $log -Encoding UTF8) } else { @() }
$result | ConvertTo-Json -Depth 5
