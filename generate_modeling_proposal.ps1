param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if ($OutputPath -eq "") {
    $outPath = Join-Path (Get-Location) "專案企劃書_Bitfinex放貸利率預測與模型評估.docx"
}
else {
    $outPath = $OutputPath
}

$tmpRoot = Join-Path (Get-Location) "_docx_build_modeling"

if (Test-Path $tmpRoot) {
    Remove-Item -LiteralPath $tmpRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "_rels") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "word") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $tmpRoot "word\_rels") | Out-Null

function Escape-Xml([string]$Text) {
    return [System.Security.SecurityElement]::Escape($Text)
}

function Paragraph([string]$Text, [string]$Style = "", [bool]$Bold = $false) {
    $escaped = Escape-Xml $Text
    $styleXml = ""
    if ($Style -ne "") {
        $styleXml = "<w:pPr><w:pStyle w:val=""$Style""/></w:pPr>"
    }
    $boldXml = ""
    if ($Bold) {
        $boldXml = "<w:rPr><w:b/></w:rPr>"
    }
    return "<w:p>$styleXml<w:r>$boldXml<w:t xml:space=""preserve"">$escaped</w:t></w:r></w:p>"
}

function Bullets([string[]]$Items) {
    $xml = ""
    foreach ($item in $Items) {
        $xml += Paragraph("• $item")
    }
    return $xml
}

function Table([string[][]]$Rows) {
    $xml = '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders></w:tblPr>'
    foreach ($row in $Rows) {
        $xml += "<w:tr>"
        foreach ($cell in $row) {
            $escaped = Escape-Xml $cell
            $xml += "<w:tc><w:tcPr><w:tcW w:w=""3000"" w:type=""dxa""/></w:tcPr><w:p><w:r><w:t xml:space=""preserve"">$escaped</w:t></w:r></w:p></w:tc>"
        }
        $xml += "</w:tr>"
    }
    $xml += "</w:tbl>"
    return $xml
}

$body = ""
$body += Paragraph "專案企劃書" "Title"
$body += Paragraph "專案執行者：＿＿江錦輝＿＿"
$body += Paragraph "諮詢講師：＿＿＿＿＿＿＿＿"
$body += Paragraph "結構型資料建模與機器學習應用" "Heading1"

$body += Paragraph "1. 我的專案主題：Bitfinex 放貸利率預測與結構型資料建模分析。"

$body += Paragraph "2. 我的專案目標" "Heading1"
$body += Paragraph "2-1 製作專案的原因：" "Heading2"
$body += Paragraph "Bitfinex 放貸市場利率會隨供需快速變動，單純查看即時資料不易判斷利率變化趨勢。本專案以公開 funding book 資料為案例，將「如何掌握放貸市場利率變化」轉化為結構型資料建模任務，練習資料載入、特徵整理、模型訓練、驗證與評估。"
$body += Paragraph "2-2 想達成的專案成果目標：" "Heading2"
$body += Paragraph "完成一個結構型資料建模專案，能將 Bitfinex 放貸市場資料整理成可訓練資料集，建立 baseline、線性迴歸、決策樹與 XGBoost 模型，預測下一個觀察時間點的放貸利率指標，並用 MAE、RMSE、R2 等指標評估與解讀模型結果。"

$body += Paragraph "3. 學習重點對應" "Heading1"
$body += Bullets @(
    "能將業務問題轉化為建模任務。",
    "掌握 Scikit-learn 標準流程：資料切分、模型訓練、驗證、評估。",
    "理解常見模型的適用情境：線性迴歸、決策樹、XGBoost。",
    "能使用適當指標評估並解讀模型結果。",
    "能將模型結果整理成 Demo 簡報，說明欄位定義、資料來源、模型流程與成果限制。"
)

$body += Paragraph "4. 業務問題與建模任務定義" "Heading1"
$body += Paragraph "4-1 業務問題：" "Heading2"
$body += Paragraph "使用者希望了解 Bitfinex 放貸市場在不同時間點的利率變化，並用歷史 funding book 資料輔助觀察市場狀態。"
$body += Paragraph "4-2 建模任務：" "Heading2"
$body += Paragraph "將業務問題轉換為監督式迴歸任務：使用目前與過去一段時間的 funding book 統計特徵，預測下一個觀察時間點的放貸利率指標。"
$body += Paragraph "4-3 評估指標：" "Heading2"
$body += Bullets @(
    "MAE：觀察平均預測誤差，容易解釋。",
    "RMSE：對較大誤差較敏感，可觀察模型是否出現明顯偏差。",
    "R2：觀察模型相對於平均值預測的解釋能力。",
    "Baseline：使用平均值預測或前一期利率預測下一期利率。"
)

$body += Paragraph "5. 資料來源與欄位規劃" "Heading1"
$body += Paragraph "資料來源以 Bitfinex 官方公開 API 為主。"
$body += Paragraph "官方文件：https://docs.bitfinex.com/reference/rest-public-book"
$body += Paragraph "API 範例：https://api-pub.bitfinex.com/v2/book/fUSD/P0?len=25"
$body += Paragraph "本次預計收集 markets：fUSD、fBTC、fETH。"
$body += Paragraph "原始欄位：" "Heading2"
$body += Bullets @(
    "market：市場代號，例如 fUSD。",
    "rate：利率。",
    "period：期間。",
    "count：彙總筆數。",
    "amount：數量。",
    "side：供給或需求方向，依 amount 正負值判斷。",
    "fetched_at：資料抓取時間。"
)
$body += Paragraph "建模特徵：" "Heading2"
$body += Bullets @(
    "market、hour、day_of_week。",
    "avg_rate、weighted_avg_rate、min_rate、max_rate。",
    "total_amount、avg_period、offer_count、demand_count。",
    "rate_spread、previous_weighted_avg_rate。"
)
$body += Paragraph "預測目標：next_weighted_avg_rate，代表下一次抓取時的加權平均利率。"

$body += Paragraph "6. 專案使用技術" "Heading1"
$body += Bullets @(
    "Python：資料處理、建模與分析主程式。",
    "Pandas：資料載入、清洗、特徵工程。",
    "Scikit-learn：資料切分、baseline、線性迴歸、決策樹、模型評估流程。",
    "XGBoost：建立進階樹模型並與 Scikit-learn 模型比較。",
    "Jupyter Notebook：紀錄探索、訓練、驗證與分析過程。",
    "Matplotlib：呈現評估結果、預測誤差、特徵重要性。",
    "簡報工具：製作 Demo 簡報與成果展示。"
)

$body += Paragraph "7. 模型規劃" "Heading1"
$body += Bullets @(
    "Baseline：使用平均值或前一期利率作為預測基準。",
    "線性迴歸：觀察特徵與目標之間是否存在近似線性關係，結果容易解釋。",
    "決策樹：捕捉非線性規則與特徵交互影響，但需注意過度擬合。",
    "XGBoost：適用於結構型資料建模，通常能提升表現，但需透過驗證集與指標判斷是否真的優於簡單模型。"
)

$body += Paragraph "8. 專案時間規劃" "Heading1"
$schedule = @(
    [string[]]@("階段", "專案執行目標", "驗收重點"),
    [string[]]@("第 1 階段", "確認資料來源、載入 Bitfinex funding book 資料、定義業務問題與建模任務。", "完成資料載入、欄位說明、業務問題、預測目標與評估指標。"),
    [string[]]@("第 2 階段", "建立資料清洗與特徵工程流程。", "完成建模資料表，包含特徵欄位與目標欄位。"),
    [string[]]@("第 3 階段", "建立 baseline、線性迴歸、決策樹模型。", "完成切分、訓練、驗證與初步模型比較。"),
    [string[]]@("第 4 階段", "建立 XGBoost 模型並進行模型評估。", "完成 MAE、RMSE、R2 評估與結果解讀。"),
    [string[]]@("第 5 階段", "整理成果報告與 Demo 簡報。", "完成程式碼、模型效能報告、欄位定義與應用情境說明。")
)
$body += Table $schedule

$body += Paragraph "9. 第一階段驗收" "Heading1"
$body += Bullets @(
    "專案內容可行性：提案內容需對應本專案學習重點，包含業務問題、建模任務、資料來源與模型流程。",
    "符合專案項目：主題需屬於結構型資料建模應用。",
    "時程規劃：提出明確執行時程與階段里程碑。",
    "本專案專屬指標：完成資料載入、明確定義業務問題與評估指標，並建立 baseline 模型規劃。"
)

$body += Paragraph "10. 完成驗收" "Heading1"
$body += Bullets @(
    "完成成果與專案主題相符：能以 Bitfinex 放貸資料完成結構型資料建模。",
    "繳交內容與第一階段提案規劃內容相呼應。",
    "具體繳交項目：完整訓練與推論程式碼、模型效能評估報告、應用情境 Demo 簡報，且簡報須包含欄位定義與資料來源。"
)

$body += Paragraph "11. 成果報告預計內容" "Heading1"
$body += Bullets @(
    "專案背景與業務問題。",
    "資料來源與欄位定義。",
    "建模任務與預測目標。",
    "資料清洗與特徵工程。",
    "Baseline 設計。",
    "Scikit-learn 訓練流程。",
    "線性迴歸、決策樹、XGBoost 模型比較。",
    "MAE、RMSE、R2 評估結果。",
    "視覺化圖表與模型解讀。",
    "專案限制與未來改進方向。"
)

$body += Paragraph "12. 專案限制與風險" "Heading1"
$body += Bullets @(
    "Bitfinex funding book 是即時資料，若收集時間不足，歷史樣本可能偏少。",
    "利率受市場供需與外部事件影響，模型結果僅能作為資料科學學習與分析示範。",
    "本專案不提供投資建議，也不進行自動下單。",
    "若 API 格式變更，資料解析邏輯需調整。",
    "若資料量不足，XGBoost 不一定優於簡單模型，需以評估指標判斷。"
)

$body += Paragraph "13. 一句話摘要" "Heading1"
$body += Paragraph "本專案以 Bitfinex 放貸市場資料為案例，訓練學習者將業務問題轉化為結構型資料建模任務，使用 Python、Pandas、Scikit-learn 與 XGBoost 完成資料切分、模型訓練、驗證、評估與結果解讀。"

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

if (Test-Path $outPath) {
    Remove-Item -LiteralPath $outPath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($outPath, [System.IO.Compression.ZipArchiveMode]::Create)
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

Write-Output $outPath
