param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputDir
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$resolvedInput = (Resolve-Path $InputPath).Path
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($resolvedInput, $false, $true)
    $pageCount = $doc.ComputeStatistics(2)
    for($page = 1; $page -le $pageCount; $page++) {
        $start = $doc.GoTo(1, 1, $page).Start
        if($page -lt $pageCount) {
            $end = $doc.GoTo(1, 1, $page + 1).Start - 1
        } else {
            $end = $doc.Content.End - 1
        }
        $range = $doc.Range($start, $end)
        $range.CopyAsPicture()
        Start-Sleep -Milliseconds 250
        $image = [System.Windows.Forms.Clipboard]::GetImage()
        if($null -eq $image) { throw "Word did not place page $page on the clipboard." }
        $path = Join-Path $OutputDir ("page-{0:D2}.png" -f $page)
        $image.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
        $image.Dispose()
    }
    Write-Output "pages=$pageCount"
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
