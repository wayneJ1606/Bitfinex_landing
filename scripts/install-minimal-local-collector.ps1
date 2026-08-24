[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter()]
    [string]$ProjectRoot = "",
    [Parameter()]
    [string]$PythonPath = "",
    [Parameter()]
    [string]$TaskName = "BitfinexLocalStableCollector",
    [Parameter()]
    [ValidateRange(0, 59)]
    [int]$Minute = 47,
    [Parameter()]
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedRoot "bitfinex_lending\local_stable_collector.py"))) {
    throw "ProjectRoot does not contain bitfinex_lending\local_stable_collector.py"
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $pythonCommand = Get-Command python -ErrorAction Stop
    $PythonPath = $pythonCommand.Source
}
$resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
$pythonwPath = Join-Path (Split-Path -Parent $resolvedPython) "pythonw.exe"
if (Test-Path -LiteralPath $pythonwPath) {
    $resolvedPython = $pythonwPath
}
$arguments = "-m bitfinex_lending.local_stable_collector --max-attempts 3 --retry-delay 2"
$firstRun = (Get-Date).Date.AddDays(1).AddMinutes($Minute)

$contract = [ordered]@{
    task_name = $TaskName
    project_root = $resolvedRoot
    python = $resolvedPython
    arguments = $arguments
    working_directory = $resolvedRoot
    first_run = $firstRun.ToString("o")
    repetition = "1 hour"
    minute = $Minute
    principal = "$env:USERDOMAIN\$env:USERNAME (Interactive, Limited)"
    enabled = [bool]$Enable
    multiple_instances = "IgnoreNew"
    start_when_available = $true
    allow_battery = $true
    execution_limit_minutes = 10
}
if (-not $Enable) {
    $contract | ConvertTo-Json -Depth 3
    Write-Output "registration=not_requested"
    exit 0
}
$action = New-ScheduledTaskAction -Execute $resolvedPython -Argument $arguments -WorkingDirectory $resolvedRoot
$trigger = New-ScheduledTaskTrigger -Once -At $firstRun -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
if ($PSCmdlet.ShouldProcess($TaskName, "Register and enable hourly local collector task")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Enable-ScheduledTask -TaskName $TaskName | Out-Null
    $contract | ConvertTo-Json -Depth 3
    Write-Output "registration=enabled"
}
