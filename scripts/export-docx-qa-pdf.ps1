param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
$input = (Resolve-Path $InputPath).Path
$output = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($input, $false, $true)
    $pages = $doc.ComputeStatistics(2)
    $doc.ExportAsFixedFormat($output, 17)
    Write-Output "pages=$pages"
    Write-Output $output
} finally {
    if($doc -ne $null) {
        try { $doc.Close($false) } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
    }
    if($word -ne $null) {
        try { $word.Quit() } catch {}
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
