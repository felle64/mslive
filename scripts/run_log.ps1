if ($args.Count -lt 1) {
  Write-Host "Usage:"
  Write-Host "  .\\scripts\\run_log.ps1 PORT [extra args...]"
  Write-Host "  .\\scripts\\run_log.ps1 --replay FILE [extra args...]"
  Write-Host ""
  Write-Host "Examples:"
  Write-Host "  .\\scripts\\run_log.ps1 COM3"
  Write-Host "  .\\scripts\\run_log.ps1 --replay logs\\ms42_log_20260114_132209.csv"
  exit 1
}

if ($args[0] -eq "--replay") {
  if ($args.Count -lt 2) {
    Write-Host "Missing replay file."
    exit 1
  }
  $file = $args[1]
  $rest = @()
  if ($args.Count -gt 2) {
    $rest = $args[2..($args.Count - 1)]
  }
  New-Item -ItemType Directory -Force -Path "logs" | Out-Null
  & python -m mslive.apps.logger_csv --replay $file @rest
  exit $LASTEXITCODE
}

$port = $args[0]
$rest = @()
if ($args.Count -gt 1) {
  $rest = $args[1..($args.Count - 1)]
}
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
& python -m mslive.apps.logger_csv --port $port @rest
exit $LASTEXITCODE
