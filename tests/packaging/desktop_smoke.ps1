# B3-09.01 packaging smoke: the real desktop exe, started from an install folder, with no other install reachable.
# Usage: powershell -File desktop_smoke.ps1 -Folder <install folder holding respected-orchestrator-desktop.exe> [-Seconds 40]
# Output: JSON {badge, alert}: the engine badge text ("Motor <version>" or "Motor yok") and the error text on the screen.
param([string]$Folder, [int]$Seconds = 40)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$empty = Join-Path $env:TEMP ("smoke-empty-" + [guid]::NewGuid().ToString('N')); New-Item -ItemType Directory $empty | Out-Null
$data = Join-Path $empty "data"; New-Item -ItemType Directory $data | Out-Null
$saved = @{ LOCALAPPDATA = $env:LOCALAPPDATA; RESPECTED_APP_DIR = $env:RESPECTED_APP_DIR; RESPECTED_DATA_DIR = $env:RESPECTED_DATA_DIR }
$env:LOCALAPPDATA = $empty            # the real per-user install must not be reachable
Remove-Item Env:RESPECTED_APP_DIR -ErrorAction SilentlyContinue
$env:RESPECTED_DATA_DIR = $data       # nothing touches real data
$proc = Start-Process (Join-Path $Folder "respected-orchestrator-desktop.exe") -PassThru -WorkingDirectory $env:TEMP
$result = [ordered]@{ folder = $Folder; badge = $null; alert = $null }
try {
  $root = [Windows.Automation.AutomationElement]::RootElement
  $deadline = (Get-Date).AddSeconds($Seconds); $main = $null
  while (-not $main -and (Get-Date) -lt $deadline) {
    $main = $root.FindFirst('Children', (New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::ProcessIdProperty), $proc.Id))
    if (-not $main) { Start-Sleep -Milliseconds 400 }
  }
  if (-not $main) { throw "main window not found" }
  $end = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $end -and -not ($result.badge -and $result.badge -notmatch "aranıyor")) {
    $names = @($main.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition) | ForEach-Object { $_.Current.Name } | Where-Object { $_ })
    $result.badge = $names | Where-Object { $_ -match "^Motor " } | Select-Object -First 1
    $result.alert = $names | Where-Object { $_ -match "^Motora bağlanılamadı|sağlıklı değil" } | Select-Object -First 1
    $result.hint = $names | Where-Object { $_ -match "kurucuyu|Kurucuyu|Onar" } | Select-Object -First 1
    Start-Sleep -Milliseconds 500
  }
} finally {
  if ($proc -and -not $proc.HasExited) { Stop-Process $proc -Force }
  Get-Process respected-orchestrator -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Folder*" } | Stop-Process -Force
  foreach ($k in $saved.Keys) { if ($saved[$k]) { Set-Item "Env:$k" $saved[$k] } else { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } }
  Remove-Item $empty -Recurse -Force -ErrorAction SilentlyContinue
}
$result | ConvertTo-Json
