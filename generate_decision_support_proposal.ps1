param(
    [string]$InputPath = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if ($InputPath -eq "") {
    $InputPath = Join-Path (Get-Location) "專案企劃書_Bitfinex放貸決策輔助系統_現實可用版.md"
}

if ($OutputPath -eq "") {
    $OutputPath = Join-Path (Get-Location) "專案企劃書_Bitfinex放貸決策輔助系統_現實可用版.docx"
}

$tmpRoot = Join-Path (Get-Location) "_docx_build_decision_support"

if (Test-Path $tmpRoot) {
    Remove-Item -LiteralPath $tmpRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "_rels") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "word") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "word\_rels") | Out-Null

function Escape-Xml([string]$Text) {
    return [System.Security.SecurityElement]::Escape($Text)
}

function Inline-Clean([string]$Text) {
    return $Text.Replace('`', "")
}

function Paragraph([string]$Text, [string]$Style = "") {
    $escaped = Escape-Xml (Inline-Clean $Text)
    $styleXml = ""
    if ($Style -ne "") {
        $styleXml = "<w:pPr><w:pStyle w:val=""$Style""/></w:pPr>"
    }
    return "<w:p>$styleXml<w:r><w:t xml:space=""preserve"">$escaped</w:t></w:r></w:p>"
}

function Table([string[][]]$Rows) {
    $xml = '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders></w:tblPr>'
    foreach ($row in $Rows) {
        $xml += "<w:tr>"
        foreach ($cell in $row) {
            $escaped = Escape-Xml (Inline-Clean $cell.Trim())
            $xml += "<w:tc><w:tcPr><w:tcW w:w=""2800"" w:type=""dxa""/></w:tcPr><w:p><w:r><w:t xml:space=""preserve"">$escaped</w:t></w:r></w:p></w:tc>"
        }
        $xml += "</w:tr>"
    }
    $xml += "</w:tbl>"
    return $xml
}

$lines = Get-Content -LiteralPath $InputPath -Encoding UTF8
$body = ""
$tableRows = New-Object System.Collections.Generic.List[string[]]

function Flush-Table {
    if ($script:tableRows.Count -gt 0) {
        $script:body += Table $script:tableRows.ToArray()
        $script:tableRows.Clear()
    }
}

foreach ($line in $lines) {
    $trimmed = $line.Trim()

    if ($trimmed -eq "") {
        Flush-Table
        continue
    }

    if ($trimmed.StartsWith("|")) {
        $cells = $trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() }
        $isSeparator = $true
        foreach ($cell in $cells) {
            if ($cell -notmatch "^-+$") {
                $isSeparator = $false
            }
        }
        if (-not $isSeparator) {
            $tableRows.Add([string[]]$cells)
        }
        continue
    }

    Flush-Table

    if ($trimmed.StartsWith("# ")) {
        $body += Paragraph $trimmed.Substring(2) "Title"
    }
    elseif ($trimmed.StartsWith("## ")) {
        $body += Paragraph $trimmed.Substring(3) "Heading1"
    }
    elseif ($trimmed.StartsWith("### ")) {
        $body += Paragraph $trimmed.Substring(4) "Heading2"
    }
    elseif ($trimmed.StartsWith("- ")) {
        $body += Paragraph ("• " + $trimmed.Substring(2))
    }
    elseif ($trimmed -match "^\d+\. ") {
        $body += Paragraph $trimmed
    }
    else {
        $body += Paragraph $trimmed
    }
}

Flush-Table

$documentXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    $body
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"@

$stylesXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:rFonts w:ascii="Microsoft JhengHei" w:eastAsia="Microsoft JhengHei"/><w:sz w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft JhengHei" w:eastAsia="Microsoft JhengHei"/><w:sz w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft JhengHei" w:eastAsia="Microsoft JhengHei"/><w:sz w:val="28"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:rFonts w:ascii="Microsoft JhengHei" w:eastAsia="Microsoft JhengHei"/><w:sz w:val="25"/></w:rPr>
  </w:style>
</w:styles>
"@

$contentTypes = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"@

$rels = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"@

$docRels = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"@

Set-Content -LiteralPath (Join-Path $tmpRoot "[Content_Types].xml") -Value $contentTypes -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmpRoot "_rels\.rels") -Value $rels -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmpRoot "word\document.xml") -Value $documentXml -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmpRoot "word\styles.xml") -Value $stylesXml -Encoding UTF8
Set-Content -LiteralPath (Join-Path $tmpRoot "word\_rels\document.xml.rels") -Value $docRels -Encoding UTF8

if (Test-Path $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($OutputPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    $files = Get-ChildItem -LiteralPath $tmpRoot -Recurse -File
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($tmpRoot.Length + 1).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $relative) | Out-Null
    }
}
finally {
    $archive.Dispose()
}

Remove-Item -LiteralPath $tmpRoot -Recurse -Force
Write-Output $OutputPath
