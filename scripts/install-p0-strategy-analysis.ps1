[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter()]
    [string]$ProjectRoot = "",
    [Parameter()]
    [string]$PythonPath = "",
    [Parameter()]
    [string]$TaskName = "BitfinexP0StrategyAnalysis",
    [Parameter()]
    [ValidatePattern("^(?:[01]\d|2[0-3]):[0-5]\d$")]
    [string]$LocalTime = "10:00",
    [Parameter()]
    [switch]$Enable
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$pipelinePath = Join-Path $resolvedRoot "bitfinex_lending\p0_strategy_pipeline.py"
if (-not (Test-Path -LiteralPath $pipelinePath)) {
    throw "ProjectRoot does not contain bitfinex_lending\p0_strategy_pipeline.py"
}
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
$resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
$pythonwPath = Join-Path (Split-Path -Parent $resolvedPython) "pythonw.exe"
if (Test-Path -LiteralPath $pythonwPath) {
    $resolvedPython = $pythonwPath
}
$arguments = "-m bitfinex_lending.p0_strategy_pipeline"

$contract = [ordered]@{
    task_name = $TaskName
    project_root = $resolvedRoot
    python = $resolvedPython
    arguments = $arguments
    working_directory = $resolvedRoot
    local_time = $LocalTime
    schedule = "daily $LocalTime local time"
    principal = "$env:USERDOMAIN\$env:USERNAME (Interactive, Limited)"
    enabled = [bool]$Enable
    multiple_instances = "IgnoreNew"
    start_when_available = $true
    allow_battery = $true
    execution_limit_minutes = 30
}
if (-not $Enable) {
    $contract | ConvertTo-Json -Depth 3
    Write-Output "registration=not_requested"
    exit 0
}

$action = New-ScheduledTaskAction -Execute $resolvedPython -Argument $arguments -WorkingDirectory $resolvedRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $LocalTime
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Register only with explicit -Enable.
if ($PSCmdlet.ShouldProcess($TaskName, "Register and enable daily P0 strategy analysis")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
    Enable-ScheduledTask -TaskName $TaskName | Out-Null
    $contract | ConvertTo-Json -Depth 3
    Write-Output "registration=enabled"
}
