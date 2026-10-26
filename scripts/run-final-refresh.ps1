[CmdletBinding()]
param(
    [Parameter()]
    [string]$ProjectRoot = "",
    [Parameter()]
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$resolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = (Get-Command python -ErrorAction Stop).Source
}
$resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
$modelCode = "from pathlib import Path; from bitfinex_lending.modeling import main, ModelingSettings; raise SystemExit(main(ModelingSettings(raw_root=Path('data/local_public/raw'), output_root=Path('data/modeling'), required_rows=168)))"

Push-Location $resolvedRoot
try {
    & $resolvedPython -c $modelCode
    if ($LASTEXITCODE -ne 0) {
        throw "bitfinex_lending.modeling failed with exit code $LASTEXITCODE"
    }

    & $resolvedPython -m bitfinex_lending.p0_strategy_pipeline
    if ($LASTEXITCODE -ne 0) {
        throw "bitfinex_lending.p0_strategy_pipeline failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Output "refresh=completed"
