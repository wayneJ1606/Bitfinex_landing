param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

if ($OutputPath -eq "") {
    $outPath = Join-Path (Get-Location) "Bitfinex放貸資料收集與資料庫_專案企劃書.docx"
}
else {
    $outPath = $OutputPath
}
$tmpRoot = Join-Path (Get-Location) "_docx_build"

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
            $xml += "<w:tc><w:tcPr><w:tcW w:w=""2400"" w:type=""dxa""/></w:tcPr><w:p><w:r><w:t xml:space=""preserve"">$escaped</w:t></w:r></w:p></w:tc>"
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
$body += Paragraph "AI-9 資料收集與資料庫（資料爬蟲）" "Heading1"

$body += Paragraph "1.我的專案主題：Bitfinex 放貸市場資料收集與資料庫建置。"

$body += Paragraph "2.我的專案目標：" "Heading1"
$body += Paragraph "2-1製作專案的原因（50-100字）：" "Heading2"
$body += Paragraph "　　加密貨幣交易所的放貸市場利率會隨供需快速變動，人工查看不易長期追蹤。本專案希望以 Bitfinex 公開資金放貸資料為主題，設計可重複執行的資料收集程式，定期抓取 USD、BTC、ETH 等資金市場的放貸掛單、利率與數量，建立可查詢的歷史資料集。"
$body += Paragraph "2-2 想達成的專案成果目標（50-100字）：" "Heading2"
$body += Paragraph "完成一套 Bitfinex 放貸資料爬蟲與資料庫，達成以下可驗收成果："
$body += Bullets @(
    "能使用 Python 程式重複抓取 Bitfinex 公開 funding book / lending 相關資料。",
    "能將幣別、利率、期間、數量、時間戳記等欄位整理後存入 SQLite 與 CSV。",
    "能產出基本統計報表，例如各幣別平均利率、最高/最低利率、放貸供給量變化。",
    "能在成果報告中說明網站/API 結構、資料流程、資料庫設計、錯誤處理與爬蟲倫理。"
)

$body += Paragraph "3.資料搜集：（靈感、參考、過往經驗）" "Heading1"
$body += Paragraph "3-1學員過往作品集分享：(首次諮詢前提供)" "Heading2"
$body += Paragraph "NO"
$body += Paragraph "連結貼上：＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"
$body += Paragraph "連結貼上：＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"
$body += Paragraph "3-2興趣參考：" "Heading2"
$body += Paragraph "Bitfinex 官方 API 文件：Public Books endpoint，可查詢 tBTCUSD、fUSD、fBTC 等交易或資金市場代號。"
$body += Paragraph "參考網址：https://docs.bitfinex.com/reference/rest-public-book"
$body += Paragraph "Bitfinex 公開 API 網址範例：https://api-pub.bitfinex.com/v2/book/fUSD/P0?len=25"
$body += Paragraph "連結貼上：https://docs.bitfinex.com/reference/rest-public-book"
$body += Paragraph "連結貼上：https://api-pub.bitfinex.com/v2/book/fUSD/P0?len=25"

$body += Paragraph "4. 專案執行規劃（可由老師協助引導填寫）" "Heading1"
$body += Paragraph "以下為你與老師諮詢後需要逐步補上的內容："
$body += Paragraph "4-1 專案名稱定錨" "Heading2"
$body += Paragraph "｜根據選擇的主題，經過老師引導後選擇最終專案製作的名稱"
$body += Paragraph "📝 專案名稱：Bitfinex 放貸利率資料收集與資料庫分析系統＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿＿"

$body += Paragraph "4-2 專案使用技術" "Heading2"
$body += Paragraph "　　使用 Python 開發資料收集程式，以 Requests 呼叫 Bitfinex 公開 API，必要時使用 BeautifulSoup 或 Selenium 分析官方文件與頁面結構。資料整理後以 pandas/csv 模組輸出 CSV，並使用 SQLite 建立資料庫；再透過 DB Browser 檢視資料表內容，確認資料欄位、筆數與查詢結果正確。"
$body += Paragraph "主要技術與工具：" 
$body += Bullets @(
    "Python：撰寫爬蟲、資料清洗、排程與報表產生。",
    "Requests：呼叫 Bitfinex 公開 API，取得 funding book 資料。",
    "BeautifulSoup / Selenium：分析目標網站結構，驗證頁面資料來源與必要動態載入流程。",
    "SQLite：設計 funding_markets、funding_offers、crawl_logs 等資料表。",
    "CSV：輸出可繳交與可檢視的結構化資料集。",
    "DB Browser：檢查資料庫內容與 SQL 查詢結果。"
)

$body += Paragraph "4-3 專案時間規劃" "Heading2"
$body += Paragraph "專案執行時程總表(mm/dd-mm/dd)"
$schedule = @(
    [string[]]@("時程", "專案執行目標", "驗收重點", "狀態"),
    [string[]]@("7/1~7/7", "確認 Bitfinex 放貸資料來源，閱讀官方 API 文件，分析 funding book 回傳格式，完成單次 fUSD 資料抓取測試；同時建立 Python 爬蟲主程式，加入幣別參數、錯誤處理、請求間隔與資料清洗流程。", "完成目標網站/API 結構分析；可成功爬取單頁或單次資料；可重複執行並抓取多個 funding symbols，例如 fUSD、fBTC、fETH；提出 CSV/SQLite 欄位草案。", "尚未開始"),
    [string[]]@("7/8~7/14", "建立 SQLite 資料庫與 CSV 輸出，完成資料表關聯、主鍵、時間戳記與爬取紀錄；完成統計查詢、成果報告與簡易使用說明，整理系統架構與關鍵技術。", "資料能正確寫入 funding_markets、funding_offers、crawl_logs；可用 DB Browser 檢視；繳交爬蟲程式、CSV 或 DB 檔、成果報告，內容與第一階段提案相呼應。", "尚未開始")
)
$body += Table $schedule

$body += Paragraph "5. 目標網站/API 結構分析" "Heading1"
$body += Paragraph "資料來源以 Bitfinex 官方公開 API 為主，避免大量解析前端頁面造成網站負擔。主要端點為 Public Books endpoint：/v2/book/{symbol}/{precision}，其中 funding market 使用 f 開頭代號，例如 fUSD、fBTC、fETH；precision 可使用 P0 取得彙總資料，len 可控制回傳筆數。"
$body += Paragraph "預計爬取欄位：" 
$body += Bullets @(
    "symbol：資金市場代號，例如 fUSD。",
    "rate：放貸年化或日化利率資料，依 API 回傳格式轉換。",
    "period：放貸期間。",
    "count：同價位資料筆數或彙總數量。",
    "amount：放貸資金數量，正負值用於區分 bid/ask 或供需方向。",
    "crawl_time：本次程式抓取時間。",
    "source_url：資料來源網址。"
)

$body += Paragraph "6. 資料庫（或 CSV）儲存結構草案" "Heading1"
$dbRows = @(
    [string[]]@("資料表", "主要欄位", "用途"),
    [string[]]@("funding_markets", "id, symbol, currency, description", "記錄要追蹤的放貸市場與幣別。"),
    [string[]]@("funding_offers", "id, market_id, rate, period, count, amount, side, crawl_time", "保存每次抓取到的放貸掛單與利率資料。"),
    [string[]]@("crawl_logs", "id, started_at, ended_at, status, message, rows_saved", "記錄每次爬蟲執行狀態，方便除錯與驗收。")
)
$body += Table $dbRows
$body += Paragraph "CSV 輸出檔預計包含：symbol、rate、period、count、amount、side、crawl_time、source_url，方便使用 Excel 或其他工具檢視。"

$body += Paragraph "7. 爬蟲倫理與法律邊界" "Heading1"
$body += Bullets @(
    "優先使用官方公開 API，不登入、不繞過權限、不抓取私人帳戶或個資。",
    "設定合理請求間隔與重試次數，避免對服務造成負擔。",
    "保存資料來源與抓取時間，報告中清楚標示資料僅供學習與研究。",
    "不將資料包裝成投資建議，不承諾放貸收益。"
)

$body += Paragraph "8. 第一階段驗收（專案計畫與規劃）" "Heading1"
$body += Paragraph "提交提案報告，須同時符合："
$body += Bullets @(
    "專案內容可行性：使用 Python、Requests、BeautifulSoup/Selenium、SQLite/CSV，與本專案學習重點對應。",
    "符合專案項目：主題為 Bitfinex 放貸資料收集與資料庫建置，屬於資料爬蟲與資料庫專案。",
    "時程規劃：提出 7/1~7/28 的階段里程碑。",
    "本專案專屬指標：完成 Bitfinex API 結構分析，成功抓取 fUSD 單次資料作為技術驗證，提出 SQLite/CSV 儲存結構草案。"
)

$body += Paragraph "9. 完成驗收（專案作品與成果報告）" "Heading1"
$body += Paragraph "提交專案成果與結案報告，須同時符合："
$body += Bullets @(
    "完成成果與專案主題相符：可收集 Bitfinex 放貸市場資料。",
    "繳交內容與第一階段提案規劃內容相呼應：資料來源、欄位、資料庫設計與時程一致。",
    "具體繳交項目：(a) 可重複執行的爬蟲程式；(b) 資料集產出 CSV 或 SQLite DB 檔；(c) 包含系統架構與關鍵技術說明的成果報告。"
)

$body += Paragraph "10. 成果報告預計內容" "Heading1"
$body += Bullets @(
    "系統架構：資料來源、爬蟲程式、資料清洗、資料庫、CSV 輸出與查詢報表。",
    "關鍵技術：HTTP 請求、API 參數、JSON 解析、資料表設計、錯誤處理、資料去重。",
    "執行結果：資料筆數、幣別數量、利率統計、DB Browser 截圖或 SQL 查詢結果。",
    "限制與改進：API 欄位限制、資料頻率、請求限制、未來可加入排程與視覺化儀表板。"
)

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
