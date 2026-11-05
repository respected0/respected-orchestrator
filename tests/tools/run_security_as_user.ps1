# FIX-01 / ADR-017: run the security set as a throw-away STANDARD local user, because the hosted runner token is elevated and the
# AppContainer boundary refuses elevated sessions. The account lives only as long as the runner VM; any failure here is a red job.
$ErrorActionPreference = 'Stop'
$work = (Get-Location).Path
$python = (Get-Command python).Source
$pythonRoot = Split-Path (Split-Path $python)            # cmd/ or Scripts/ lives next to the install root
if (-not (Test-Path (Join-Path $pythonRoot 'python.exe'))) { $pythonRoot = Split-Path $python }
$name = 'orchsec'
$password = ConvertTo-SecureString ([guid]::NewGuid().ToString('N') + 'Aa1!') -AsPlainText -Force
New-LocalUser -Name $name -Password $password -AccountNeverExpires | Out-Null
foreach ($path in @($work, $pythonRoot)) { icacls $path /grant "${name}:(OI)(CI)F" /T /C /Q | Out-Null }
$out = Join-Path $work 'security-run.log'
$manifest = Join-Path $work 'security-manifest.json'
$credential = New-Object System.Management.Automation.PSCredential($name, $password)
# Start-Process -Credential gives the child the new user's own environment, so pass what the job needs explicitly.
$inner = "`$env:PATH='$env:PATH'; `$env:GITHUB_SHA='$env:GITHUB_SHA'; `$env:ImageVersion='$env:ImageVersion'; `$env:PYTHONUTF8='1'; " +
  "& '$python' tests/tools/run_security_ci.py run '$manifest' *> '$out.stdout'; exit `$LASTEXITCODE"
$process = Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile', '-Command', $inner `
  -WorkingDirectory $work -Credential $credential -LoadUserProfile -Wait -PassThru
Get-Content "$out.stdout" -ErrorAction SilentlyContinue
if ($process.ExitCode -ne 0) { throw "security run failed with exit code $($process.ExitCode)" }
