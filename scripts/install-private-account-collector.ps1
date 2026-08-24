param(
    [string]$ProjectRoot = (Get-Location).Path,
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
$taskName = "BitfinexPrivateAccountCollector"
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$modulePath = Join-Path $resolvedRoot "bitfinex_lending\private_account_collector.py"

if (-not (Test-Path -LiteralPath $modulePath)) {
    throw "ProjectRoot does not contain bitfinex_lending\private_account_collector.py"
}

$pythonCommand = Get-Command python -ErrorAction Stop
$python = Join-Path (Split-Path -Parent $pythonCommand.Source) "pythonw.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = $pythonCommand.Source
}
$arguments = "-m bitfinex_lending.private_account_collector --max-attempts 3 --retry-delay 2"

if (-not $Enable) {
    Write-Output "Preview only; no task was registered."
    Write-Output "Task: $taskName"
    Write-Output "Python: $python"
    Write-Output "Arguments: $arguments"
    Write-Output "WorkingDirectory: $resolvedRoot"
    Write-Output "Schedule: every 5 minutes"
    Write-Output "Run with -Enable to register the task."
    return
}

$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $resolvedRoot
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date.AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Output "Registered and enabled task: $taskName"
