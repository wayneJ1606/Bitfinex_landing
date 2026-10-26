param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutputPath = "",
    [string]$PdfOutputPath = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutputPath) {
    $OutputPath = Join-Path $ProjectRoot "deliverables\Bitfinex_放貸決策輔助系統_結案報告_最終版.docx"
}
$outputDir = Split-Path -Parent $OutputPath
$assetDir = Join-Path $outputDir "report_assets"
New-Item -ItemType Directory -Force -Path $outputDir, $assetDir | Out-Null

Add-Type -AssemblyName System.Drawing

$navy = [System.Drawing.Color]::FromArgb(31, 78, 121)
$blue = [System.Drawing.Color]::FromArgb(68, 114, 196)
$paleBlue = [System.Drawing.Color]::FromArgb(221, 235, 247)
$gray = [System.Drawing.Color]::FromArgb(89, 89, 89)
$lightGray = [System.Drawing.Color]::FromArgb(242, 242, 242)
$green = [System.Drawing.Color]::FromArgb(112, 173, 71)
$orange = [System.Drawing.Color]::FromArgb(237, 125, 49)
$red = [System.Drawing.Color]::FromArgb(192, 0, 0)
$fontName = "Microsoft JhengHei"

function New-Canvas([int]$Width, [int]$Height) {
    $bmp = New-Object System.Drawing.Bitmap($Width, $Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::White)
    return @($bmp, $g)
}

function Save-Canvas($Bitmap, $Graphics, [string]$Path) {
    $Graphics.Dispose()
    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
}

function Draw-CenteredText($Graphics, [string]$Text, $Font, $Brush, [System.Drawing.RectangleF]$Rect) {
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $Graphics.DrawString($Text, $Font, $Brush, $Rect, $sf)
    $sf.Dispose()
}

function New-FlowDiagram([string]$Path) {
    $canvas = New-Canvas 1600 520; $bmp=$canvas[0]; $g=$canvas[1]
    $titleFont = New-Object System.Drawing.Font($fontName, 28, [System.Drawing.FontStyle]::Bold)
    $boxFont = New-Object System.Drawing.Font($fontName, 18, [System.Drawing.FontStyle]::Bold)
    $smallFont = New-Object System.Drawing.Font($fontName, 14)
    $blackBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
    $whiteBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $navyBrush = New-Object System.Drawing.SolidBrush($navy)
    $paleBrush = New-Object System.Drawing.SolidBrush($paleBlue)
    $redBrush = New-Object System.Drawing.SolidBrush($red)
    $pen = New-Object System.Drawing.Pen($blue, 4)
    $arrow = New-Object System.Drawing.Drawing2D.AdjustableArrowCap(7, 7)
    $pen.CustomEndCap = $arrow
    Draw-CenteredText $g "Bitfinex 放貸決策輔助系統資料流程" $titleFont $blackBrush ([System.Drawing.RectangleF]::new(0,15,1600,55))
    $labels = @(
        @("Bitfinex API", "Funding Book、Ticker`nStats、Candles、Price"),
        @("定時收集", "GitHub Actions 與`nWindows 背景排程"),
        @("資料保存", "原始 CSV、SQLite`nMetadata 與每日分檔"),
        @("特徵與模型", "每小時特徵、下一時點`n利率預測與效能評估"),
        @("策略與展示", "成交代理、等待與扣費`n策略比較及 Dashboard")
    )
    for($i=0;$i -lt $labels.Count;$i++) {
        $x = 35 + $i*313
        $rect = [System.Drawing.RectangleF]::new($x,145,250,210)
        $fill = if($i % 2 -eq 0){$navyBrush}else{$paleBrush}
        $g.FillRectangle($fill,$rect)
        $g.DrawRectangle((New-Object System.Drawing.Pen($navy,2)),$x,145,250,210)
        $textBrush = if($i % 2 -eq 0){$whiteBrush}else{$blackBrush}
        Draw-CenteredText $g $labels[$i][0] $boxFont $textBrush ([System.Drawing.RectangleF]::new($x+10,165,230,45))
        Draw-CenteredText $g $labels[$i][1] $smallFont $textBrush ([System.Drawing.RectangleF]::new($x+12,215,226,110))
        if($i -lt $labels.Count-1) { $g.DrawLine($pen,$x+255,250,$x+303,250) }
    }
    $noteFont = New-Object System.Drawing.Font($fontName, 14, [System.Drawing.FontStyle]::Italic)
    Draw-CenteredText $g "安全邊界：只讀取、分析與展示，不自動下單、撤單、轉帳或提領" $noteFont $redBrush ([System.Drawing.RectangleF]::new(120,405,1360,45))
    Save-Canvas $bmp $g $Path
}

function New-R2Chart([string]$Path, $Rows) {
    $canvas = New-Canvas 1400 720; $bmp=$canvas[0]; $g=$canvas[1]
    $titleFont = New-Object System.Drawing.Font($fontName, 26, [System.Drawing.FontStyle]::Bold)
    $axisFont = New-Object System.Drawing.Font($fontName, 14)
    $labelFont = New-Object System.Drawing.Font($fontName, 13)
    $black = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
    $gridPen = New-Object System.Drawing.Pen([System.Drawing.Color]::LightGray,1)
    Draw-CenteredText $g "模型驗證集 R² 比較" $titleFont $black ([System.Drawing.RectangleF]::new(0,10,1400,50))
    $markets=@('fBTC','fETH','fUSD','fUST'); $models=@('baseline_previous','decision_tree','xgboost')
    $colors=@($green,$blue,$orange)
    $left=110; $top=90; $width=1210; $height=510; $min=-11.0; $max=1.0
    for($v=-10;$v -le 0;$v+=2) {
        $y=$top + ($max-$v)/($max-$min)*$height
        $g.DrawLine($gridPen,$left,$y,$left+$width,$y)
        $g.DrawString([string]$v,$axisFont,$black,45,$y-10)
    }
    $zeroY=$top + ($max-0)/($max-$min)*$height
    $g.DrawLine((New-Object System.Drawing.Pen([System.Drawing.Color]::Black,2)),$left,$zeroY,$left+$width,$zeroY)
    for($mi=0;$mi -lt $markets.Count;$mi++) {
        $groupX=$left+55+$mi*300
        for($j=0;$j -lt $models.Count;$j++) {
            $r=$Rows | Where-Object { $_.market -eq $markets[$mi] -and $_.model_name -eq $models[$j] } | Select-Object -First 1
            $val=[double]$r.r2
            $yVal=$top + ($max-$val)/($max-$min)*$height
            $barX=$groupX+$j*82; $barW=58
            $brush=New-Object System.Drawing.SolidBrush($colors[$j])
            if($val -ge 0){ $g.FillRectangle($brush,$barX,$yVal,$barW,$zeroY-$yVal) } else { $g.FillRectangle($brush,$barX,$zeroY,$barW,$yVal-$zeroY) }
            $txt=('{0:N2}' -f $val)
            $g.DrawString($txt,$labelFont,$black,$barX-8,[Math]::Min($yVal+5,$top+$height-25))
            $brush.Dispose()
        }
        $g.DrawString($markets[$mi],$axisFont,$black,$groupX+55,$top+$height+12)
    }
    $legend=@('前一值 Baseline','決策樹','XGBoost')
    for($j=0;$j -lt 3;$j++) {
        $x=330+$j*280; $b=New-Object System.Drawing.SolidBrush($colors[$j]); $g.FillRectangle($b,$x,665,28,18); $g.DrawString($legend[$j],$axisFont,$black,$x+40,660); $b.Dispose()
    }
    Save-Canvas $bmp $g $Path
}

function New-StrategyChart([string]$Path, $Results) {
    $canvas = New-Canvas 1400 720; $bmp=$canvas[0]; $g=$canvas[1]
    $titleFont = New-Object System.Drawing.Font($fontName, 26, [System.Drawing.FontStyle]::Bold)
    $axisFont = New-Object System.Drawing.Font($fontName, 14)
    $labelFont = New-Object System.Drawing.Font($fontName, 13, [System.Drawing.FontStyle]::Bold)
    $black = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
    Draw-CenteredText $g "1,000 USDT 策略比較  2 天  等待上限 1 小時" $titleFont $black ([System.Drawing.RectangleF]::new(0,10,1400,55))
    $wanted=@(
        @('optimized_without_prediction','highest_return','最佳化最高收益'),
        @('optimized_without_prediction','stable_alternative','穩健替代'),
        @('fixed_median','fixed_median','固定中位利率'),
        @('quick_fill','quick_fill','低利率快速成交'),
        @('frr','frr','FRR 市場基準')
    )
    $data=@()
    foreach($w in $wanted) {
        $r=$Results | Where-Object { $_.asset -eq 'USDT' -and $_.principal -eq '1000' -and $_.strategy_type -eq $w[0] -and $_.portfolio_type -eq $w[1] -and $_.period_days -eq '[2]' -and $_.wait_hours -eq '[1]' } | Select-Object -First 1
        if($r){ $data += [pscustomobject]@{Label=$w[2]; Value=[double]$r.net_interest; Fill=[double]$r.fill_probability; Idle=[double]$r.idle_fraction} }
    }
    $max=($data.Value | Measure-Object -Maximum).Maximum*1.18
    $left=320; $top=105; $barH=70; $gap=30; $width=930
    for($i=0;$i -lt $data.Count;$i++) {
        $y=$top+$i*($barH+$gap); $d=$data[$i]; $w=[int]($d.Value/$max*$width)
        $c=if($i -eq 0){$navy}elseif($i -eq 1){$green}else{$blue}
        $brush=New-Object System.Drawing.SolidBrush($c)
        $g.DrawString($d.Label,$axisFont,$black,35,$y+18)
        $g.FillRectangle($brush,$left,$y,$w,$barH)
        $g.DrawString(('{0:N3} USDT' -f $d.Value),$labelFont,(New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)),$left+12,$y+20)
        $g.DrawString(('成交代理 {0:P1}  閒置 {1:P1}' -f $d.Fill,$d.Idle),$axisFont,$black,$left+$w+18,$y+18)
        $brush.Dispose()
    }
    $noteFont=New-Object System.Drawing.Font($fontName,13,[System.Drawing.FontStyle]::Italic)
    $redBrush=New-Object System.Drawing.SolidBrush($red)
    $g.DrawString("正式資料快照：2026-10-26。公開成交代理仍不等同本人實際成交。",$noteFont,$redBrush,250,645)
    Save-Canvas $bmp $g $Path
}

function New-MaturityGraphic([string]$Path) {
    $canvas = New-Canvas 1400 360; $bmp=$canvas[0]; $g=$canvas[1]
    $titleFont=New-Object System.Drawing.Font($fontName,24,[System.Drawing.FontStyle]::Bold)
    $font=New-Object System.Drawing.Font($fontName,16)
    $bold=New-Object System.Drawing.Font($fontName,18,[System.Drawing.FontStyle]::Bold)
    $black=New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
    Draw-CenteredText $g "USDT 公開資料成熟度" $titleFont $black ([System.Drawing.RectangleF]::new(0,8,1400,48))
    $left=130; $top=125; $width=1140; $height=62; $pct=1.0
    $g.FillRectangle((New-Object System.Drawing.SolidBrush($lightGray)),$left,$top,$width,$height)
    $g.FillRectangle((New-Object System.Drawing.SolidBrush($green)),$left,$top,[int]($width*$pct),$height)
    $g.DrawRectangle((New-Object System.Drawing.Pen($gray,2)),$left,$top,$width,$height)
    Draw-CenteredText $g "目前 62.96 天" $bold $black ([System.Drawing.RectangleF]::new(110,205,360,45))
    Draw-CenteredText $g "正式門檻 60 天" $bold $black ([System.Drawing.RectangleF]::new(965,205,330,45))
    $greenBrush=New-Object System.Drawing.SolidBrush($green)
    Draw-CenteredText $g "已達正式門檻：1,512 筆每小時資料，完整率 100%，最長缺口 1 小時" $font $greenBrush ([System.Drawing.RectangleF]::new(120,275,1160,45))
    Save-Canvas $bmp $g $Path
}

$evalRows = Import-Csv (Join-Path $ProjectRoot "data\modeling\model_evaluations.csv")
$strategyRows = Import-Csv (Join-Path $ProjectRoot "data\modeling\p0_strategy\latest\strategy_results.csv")
$flowPng = Join-Path $assetDir "system_flow.png"
$r2Png = Join-Path $assetDir "model_r2.png"
$strategyPng = Join-Path $assetDir "strategy_comparison.png"
$maturityPng = Join-Path $assetDir "data_maturity.png"
New-FlowDiagram $flowPng
New-R2Chart $r2Png $evalRows
New-StrategyChart $strategyPng $strategyRows
New-MaturityGraphic $maturityPng

$word = $null
$doc = $null
try {
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Add()
$doc.PageSetup.TopMargin = $word.CentimetersToPoints(2.2)
$doc.PageSetup.BottomMargin = $word.CentimetersToPoints(2.0)
$doc.PageSetup.LeftMargin = $word.CentimetersToPoints(2.4)
$doc.PageSetup.RightMargin = $word.CentimetersToPoints(2.2)

function Set-RunFont($range, [double]$size=11, [bool]$bold=$false, [int]$color=0) {
    $range.Font.NameFarEast = $fontName
    $range.Font.Name = $fontName
    $range.Font.Size = $size
    $range.Font.Bold = [int]$bold
    $range.Font.Color = $color
}
function Add-Paragraph([string]$text="", [double]$size=11, [bool]$bold=$false, [int]$align=0, [double]$after=7) {
    $start = $doc.Content.End - 1
    $range = $doc.Range($start, $start)
    $range.InsertAfter($text)
    $p = $doc.Range($start, $start + $text.Length).Paragraphs.Item(1)
    Set-RunFont $p.Range $size $bold 0
    $p.Alignment=$align; $p.SpaceAfter=$after; $p.LineSpacingRule=1
    $p.Range.InsertParagraphAfter()
    return $p
}
function Add-Heading([string]$text, [int]$level=1) {
    $start = $doc.Content.End - 1
    $range = $doc.Range($start, $start)
    $range.InsertAfter($text)
    $p = $doc.Range($start, $start + $text.Length).Paragraphs.Item(1)
    $p.Style = if($level -eq 1){-2}else{-3}
    $headingSize = if($level -eq 1){17}else{13}
    Set-RunFont $p.Range $headingSize $true 0
    $p.SpaceBefore=if($level -eq 1){14}else{9}; $p.SpaceAfter=6; $p.KeepWithNext=$true
    $p.Range.InsertParagraphAfter()
    return $p
}
function Add-Bullets([string[]]$items) {
    foreach($item in $items) {
        $p=Add-Paragraph $item 10.5 $false 0 3
        $p.Range.ListFormat.ApplyBulletDefault()
        $p.LeftIndent=$word.CentimetersToPoints(0.65)
        $p.FirstLineIndent=$word.CentimetersToPoints(-0.35)
    }
}
function Shade-Cell($cell,[string]$hex) {
    $c = [System.Drawing.ColorTranslator]::FromHtml("#$hex")
    $cell.Shading.BackgroundPatternColor = $c.R + (256 * $c.G) + (65536 * $c.B)
}
function Add-Table([string[]]$headers, [object[]]$rows, [double[]]$widths=@()) {
    $range=$doc.Range($doc.Content.End-1,$doc.Content.End-1)
    $table=$doc.Tables.Add($range,$rows.Count+1,$headers.Count)
    $table.Borders.Enable=1; $table.AllowAutoFit=$true; $table.Rows(1).HeadingFormat=$true
    $table.Rows.AllowBreakAcrossPages=$false
    for($c=1;$c -le $headers.Count;$c++) {
        $cell=$table.Cell(1,$c); $cell.Range.Text=$headers[$c-1]; Set-RunFont $cell.Range 9.5 $true 16777215; Shade-Cell $cell "1F4E79"; $cell.VerticalAlignment=1
        if($widths.Count -eq $headers.Count){$cell.Width=$word.CentimetersToPoints($widths[$c-1])}
    }
    for($r=0;$r -lt $rows.Count;$r++) {
        for($c=0;$c -lt $headers.Count;$c++) {
            $cell=$table.Cell($r+2,$c+1); $cell.Range.Text=[string]$rows[$r][$c]; Set-RunFont $cell.Range 9 $false 0; $cell.VerticalAlignment=1
            if($r%2 -eq 1){Shade-Cell $cell "F2F6FA"}
        }
    }
    $table.Range.ParagraphFormat.SpaceAfter=0; $table.Range.ParagraphFormat.SpaceBefore=0
    $afterTable = $doc.Range($doc.Content.End-1, $doc.Content.End-1)
    $afterTable.InsertParagraphAfter()
    return $table
}
function Add-Figure([string]$path,[string]$caption,[double]$widthCm=16.0) {
    $pictureRange=$doc.Range($doc.Content.End-1,$doc.Content.End-1)
    $shape=$pictureRange.InlineShapes.AddPicture($path,$false,$true)
    $shape.LockAspectRatio=-1; $shape.Width=$word.CentimetersToPoints($widthCm)
    $p=$shape.Range.Paragraphs.Item(1)
    $p.Alignment=1; $p.KeepWithNext=$true; $p.SpaceAfter=0
    $p.Range.InsertParagraphAfter()
    $cap=Add-Paragraph $caption 9 $false 1 9; $cap.KeepWithNext=$false
}
function Page-Break {
    $range=$doc.Range($doc.Content.End-1,$doc.Content.End-1)
    $range.InsertBreak(7)
}

# Cover
$p=Add-Paragraph "Bitfinex 放貸決策輔助系統" 28 $true 1 12; $p.Style=-63; Set-RunFont $p.Range 28 $true 0
Add-Paragraph "專案成果與結案報告最終版" 18 $false 1 30 | Out-Null
Add-Paragraph "公開市場資料收集  利率預測  放貸策略比較  決策 Dashboard" 12 $false 1 55 | Out-Null
Add-Figure $flowPng "圖 1  系統由資料收集一路連接至模型與策略展示" 16.0
Add-Paragraph "報告日期  2026 年 10 月 26 日" 11 $false 1 4 | Out-Null
Add-Paragraph "用途  專案作品驗收與成果說明" 10 $false 1 4 | Out-Null
Page-Break

Add-Heading "摘要" 1 | Out-Null
Add-Paragraph "本專案已完成 Bitfinex 放貸市場公開資料的定時收集、原始資料保存、每小時特徵工程、下一時點利率預測模型、模型效能評估、實驗性 USDT 放貸策略比較，以及唯讀 Dashboard。系統的目的不是自動下單，而是把利率、成交可能性、等待時間、資金閒置與手續費放在同一個畫面中，協助使用者判斷不同掛單方案的取捨。" | Out-Null
Add-Paragraph "基礎利率模型已能針對 fBTC、fETH、fUSD 與 fUST 完成訓練及推論。在目前驗證資料中，四個市場都由簡單的前一期基準取得最佳 R²，表示複雜模型尚未提供穩定增益。最佳化策略層已能輸出 1,400 筆候選結果；截至 2026 年 10 月 26 日，USDT 公開歷史達 62.96 天、完整率 100%，已超過 60 天正式門檻並完成 walk-forward 驗證。結果仍屬研究與決策輔助，不構成投資建議。" | Out-Null
Add-Heading "驗收項目對照" 2 | Out-Null
Add-Table @("驗收要求","本專案對應成果","狀態") @(
    @("主題相符","以 Bitfinex Funding 資料建立利率預測及放貸決策輔助","完成"),
    @("呼應第一階段提案","保留 fUSD、fBTC、fETH 收集、特徵、模型、評估與 Demo 主線","完成"),
    @("完整訓練與推論程式碼","程式碼、測試與執行指令均保留於專案及 GitHub","完成"),
    @("模型效能評估","使用時間順序切分與 MAE、RMSE、R² 比較五種模型","完成"),
    @("應用情境 Demo","Dashboard 呈現本金、期限、策略、成交代理、等待、淨利與限制","完成，正式資料門檻已達")
) @(3.4,9.0,3.0) | Out-Null

Add-Heading "一 分析目的" 1 | Out-Null
Add-Paragraph "Bitfinex 放貸並不是利率越高就一定賺得越多。低利率掛單通常較容易成交，但單位時間收益較少；高利率掛單可能獲得較高利息，也可能因長時間未成交而讓資金閒置。本專案將問題拆成兩層：第一層預測下一個時間點的市場利率，第二層根據歷史市場狀態比較不同利率、期限與等待條件下的預期結果。" | Out-Null
Add-Heading "第一階段提案與最終成果的關係" 2 | Out-Null
Add-Table @("原始提案內容","最終實作","調整原因") @(
    @("收集 fUSD、fBTC、fETH Funding Book","完成 GitHub 與本機雙來源公開收集","降低 GitHub 排程延遲造成的缺漏"),
    @("建立下一時點利率預測","完成 Baseline、線性迴歸、決策樹與 XGBoost","維持原始模型主題"),
    @("以 MAE、RMSE、R² 評估","完成時間順序 80／20 驗證","避免隨機切分洩漏未來資訊"),
    @("提供 Demo","完成唯讀 Dashboard","讓結果可被非程式使用者閱讀"),
    @("未明確定義策略最佳化","新增 USDT 最佳化策略層","依業師建議連接成交、等待、閒置與淨收益")
) @(4.6,6.2,4.8) | Out-Null

Add-Heading "二 分析方法" 1 | Out-Null
Add-Heading "系統架構與資料流" 2 | Out-Null
Add-Figure $flowPng "圖 2  完整資料與模型處理流程" 16.0
Add-Paragraph "GitHub Actions 持續保留公開 Funding Book 歷史；本機公開收集器補足較穩定的每小時市場資料；私人收集器以 Bitfinex 唯讀權限記錄本人的 Offers、Trades、Loans 與 Credits。公開與私人資料分開保存，私人資料不推送 GitHub。模型及 Dashboard 只讀取整理後的資料，不具備任何下單權限。" | Out-Null

Add-Heading "資料來源與欄位定義" 2 | Out-Null
Add-Table @("資料類型","來源","主要用途","保存位置") @(
    @("Funding Book","Bitfinex Public Books API","利率、期限、供需深度與成交代理","data/raw、data/local_public/raw"),
    @("Ticker 與 Stats","Bitfinex Public API","市場利率與近期統計補充","data/local_public/market"),
    @("Candles 與價格","Bitfinex Public API","市場情境及 BTC／ETH 對 USDT 換算","data/local_public/market"),
    @("帳戶 Funding 事件","Bitfinex Auth API 唯讀權限","未來校正本人真實成交與等待","data/account，永不推送 GitHub"),
    @("模型與策略結果","本專案離線程式產生","模型評估、回測、Dashboard","data/modeling")
) @(3.2,4.1,5.1,4.0) | Out-Null
Add-Heading "Funding Book 原始欄位" 2 | Out-Null
Add-Table @("欄位","意義","來源或計算") @(
    @("market","放貸市場代碼，例如 fUSD、fBTC、fETH、fUST","API 查詢條件"),
    @("rate","每日放貸利率，計算時不是直接當成年利率","Bitfinex API"),
    @("period","掛單要求的放貸天數","Bitfinex API"),
    @("count","該價位聚合筆數","Bitfinex API"),
    @("amount","資金量；正負號區分 offer 與 demand","Bitfinex API"),
    @("fetched_at","抓取時間，採 ISO 8601 UTC","收集器"),
    @("run_id","單次收集識別碼，用於追查與去重","收集器")
) @(3.1,8.4,5.0) | Out-Null
Add-Heading "每小時建模特徵" 2 | Out-Null
Add-Paragraph "原始 Funding Book 依市場與時間聚合為每小時資料。主要特徵包括 hour、day_of_week、avg_rate、weighted_avg_rate、min_rate、max_rate、total_amount、avg_period、offer_count、demand_count、rate_spread、previous_weighted_avg_rate、rate_change 與 amount_change。預測目標為下一時間點的 weighted_avg_rate。" | Out-Null
Add-Paragraph "有效特徵並不是原始 CSV 的每一行。只有在同一小時內具備必要欄位、可正確聚合，且能與下一期目標對齊的紀錄，才會進入模型訓練。" | Out-Null

Page-Break
Add-Heading "資料收集與保存" 2 | Out-Null
Add-Bullets @(
    "GitHub Actions 設定為定時處理公開資料；跨平台鎖已提交至 master，並於 Ubuntu 遠端驗收成功（GitHub Actions run 39687079671）。",
    "本機公開收集器每小時執行，公開資料與 GitHub 原始資料分開保存。",
    "私人帳戶收集器每 5 分鐘以唯讀權限執行，私人內容只留在本機。",
    "CSV 方便查閱與交換；SQLite 提供去重、事件保存與後續查詢；Metadata 記錄時間、來源、成功或失敗狀態。",
    "收集工作由 Windows 工作排程器呼叫，關閉 PowerShell 視窗不影響後續排程。"
)
Add-Paragraph "資料採每日分檔，避免單一 CSV 無限制增長。公開資料可供業師從 GitHub 查核，私人 API 金鑰及帳戶內容不會進入版本控制。" | Out-Null

Add-Heading "模型訓練與推論" 2 | Out-Null
Add-Paragraph "模型依時間順序以 80％ 訓練、20％ 驗證，避免把未來資料混入過去。評估模型包含平均值 Baseline、前一值 Baseline、線性迴歸、決策樹與 XGBoost。所有模型都接收相同的每小時特徵，預測下一時間點的加權平均利率。" | Out-Null
Add-Heading "XGBoost 白話說明" 2 | Out-Null
Add-Paragraph "XGBoost 可以想成一組輪流修正錯誤的小型決策樹。第一棵樹先做粗略預測，下一棵樹專門學習前一棵樹預測錯誤的地方，最後把多棵樹的結果加總。它能處理非線性與特徵交互作用，但資料太少時也可能只記住歷史，因此必須與簡單 Baseline 公平比較。" | Out-Null
Page-Break
Add-Heading "主要程式與執行方式" 2 | Out-Null
Add-Table @("功能","主要程式或模組","輸出") @(
    @("公開資料收集","bitfinex_lending collector 與 local_stable_collector","CSV、SQLite、Metadata"),
    @("特徵與基礎模型","python -m bitfinex_lending.modeling","modeling_features、evaluations、predictions"),
    @("模型解讀與圖表","model_report、prediction_chart","Markdown 與預測圖"),
    @("最佳化策略分析","python -m bitfinex_lending.p0_strategy_pipeline","策略 CSV、JSON、報告與 Dashboard"),
    @("一鍵完整更新","scripts/run-final-refresh.ps1","模型、策略與 Dashboard"),
    @("自動驗證","python -m pytest -q","374 passed、1 deselected")
) @(3.7,7.8,5.0) | Out-Null

Add-Heading "三 分析結果" 1 | Out-Null
Add-Heading "模型效能評估" 2 | Out-Null
Add-Paragraph "MAE 是平均絕對誤差，越小越好；RMSE 會更重視較大的誤差，越小越好；R² 表示模型解釋變動的程度，接近 1 較佳，低於 0 代表甚至不如用固定平均值預測。" | Out-Null
Add-Table @("市場","有效資料","最佳模型","MAE","RMSE","R²") @(
    @("fBTC","1,693","前一期基準","2.2501e-10","5.9266e-10","-0.1423"),
    @("fETH","1,693","前一期基準","1.8876e-05","3.3860e-05","-0.0151"),
    @("fUSD","1,693","前一期基準","4.7159e-06","1.0205e-05","0.7676"),
    @("fUST","1,512","前一期基準","7.6615e-06","1.5461e-05","0.8938")
) @(2.4,2.4,4.1,2.7,2.7,2.3) | Out-Null
Add-Figure $r2Png "圖 3  複雜模型未必優於簡單的前一值 Baseline" 15.8
Add-Paragraph "目前四個市場都由前一期基準取得最佳 R²。fUSD 與 fUST 分別達 0.7676 與 0.8938，顯示短期利率延續性明顯；fBTC 與 fETH 的最佳 R² 仍為負值，表示這兩個市場目前連簡單基準也無法穩定解釋驗證期變動。複雜模型尚未提供一致增益，後續仍須持續監控跨期表現。" | Out-Null

$predCharts=@(
    @("data\modeling\prediction_fBTC.svg","圖 4  fBTC 驗證集實際值與預測值"),
    @("data\modeling\prediction_fETH.svg","圖 5  fETH 驗證集實際值與預測值"),
    @("data\modeling\prediction_fUSD.svg","圖 6  fUSD 驗證集實際值與預測值"),
    @("data\modeling\prediction_fUST.svg","圖 7  fUST 驗證集實際值與預測值")
)
foreach($item in $predCharts) {
    Page-Break
    $p=Join-Path $ProjectRoot $item[0]
    if(Test-Path $p){ Add-Figure $p $item[1] 14.5 }
}

Page-Break
Add-Heading "最佳化放貸策略比較" 2 | Out-Null
Add-Paragraph "基礎模型回答下一時間點利率可能落在哪裡；最佳化策略層再回答應該掛多少利率、借出幾天，以及等待未成交是否會讓高利率失去優勢。候選本金為 1,000 至 10,000 USDT，每 1,000 USDT 可視為一個拆單單位，期限比較 2、5、10 與 30 天。收益計算已納入 Bitfinex 放貸收益 15％ 手續費。" | Out-Null
Add-Figure $strategyPng "圖 8  最新 1,000 USDT 策略比較示例" 15.8
Add-Table @("策略","利率概念","成交代理","淨利息","用途") @(
    @("最佳化含預測","依模型與成交代理選擇預期淨收益最高者","71.43％","4.749 USDT","觀察模型輔助效果"),
    @("最佳化未含預測","只依歷史市場條件最佳化","71.43％","4.749 USDT","比較預測增益"),
    @("穩健替代","較重視成交穩定","92.86％","3.700 USDT","降低結果波動"),
    @("快速成交","較低利率換取較高成交代理","99.67％","2.969 USDT","快速成交基準"),
    @("FRR","Bitfinex 市場參考利率","71.43％","4.749 USDT","市場基準")
) @(3.1,5.2,2.7,2.7,3.4) | Out-Null
Add-Paragraph "以上為本金 1,000 USDT、名目期間 2 天、等待上限 1 小時的正式歷史驗證結果。含預測、未含預測的最佳化結果與 FRR 相同，代表目前尚未證明模型帶來額外淨收益；資料門檻與 walk-forward 驗證雖已完成，結果仍不等於未來保證收益。" | Out-Null

Add-Heading "Dashboard 應用情境" 2 | Out-Null
Add-Paragraph "使用者開啟 Dashboard 後，選擇本金與借出期限，系統會從最新模型輸出中篩選候選策略，顯示利率、成交代理、平均等待、閒置比例、扣費後淨利息與期末本金。使用者可比較追求較高報酬與追求較快成交的差異，再自行決定是否到 Bitfinex 人工掛單。" | Out-Null
Add-Heading "Dashboard 輸出欄位" 2 | Out-Null
Add-Table @("顯示欄位","代表意義","閱讀方式") @(
    @("本金","本次模擬可運用的 USDT","1,000 至 10,000 USDT"),
    @("期限","候選放貸天數","2、5、10、30 天"),
    @("每日利率","掛單使用的日利率","不是直接等於年化報酬"),
    @("成交代理","依公開市場深度估計的成交可能性","不等於本人佇列順位的真實成交率"),
    @("平均等待","估計資金等待成交的時間","等待越久，資金閒置越多"),
    @("閒置比例","模擬期間未產生利息的資金時間占比","越低代表資金利用較充分"),
    @("淨利息","利息扣除 15％ 手續費後的估計值","用來比較策略，不代表保證收益"),
    @("期末本金","本金加上淨利息","方便使用者理解模擬結果")
) @(3.2,7.0,5.1) | Out-Null
Add-Paragraph "目前 Dashboard 為唯讀工具，不會讀取或顯示 API 金鑰，也不會代表使用者下單。這個安全邊界符合專案的研究與決策輔助定位。" | Out-Null

Add-Heading "資料成熟度與可靠性" 2 | Out-Null
Add-Figure $maturityPng "圖 9  USDT 公開資料已達正式門檻" 15.8
Add-Paragraph "截至 2026 年 10 月 26 日，USDT 公開歷史達 62.96 天，共 1,512 筆每小時資料，完整率 100%，最長缺口 1 小時，並可產生 1,400 筆策略結果。資料門檻與 walk-forward 驗證均已完成，因此產品流程、資料欄位、計算及 Dashboard 可進入正式驗收；但策略仍須接受後續滾動監控。" | Out-Null
Add-Table @("可靠性項目","目前狀態","正式完成條件") @(
    @("公開市場連續性","62.96 天、完整率 100%、最長缺口 1 小時","已達 60 天門檻"),
    @("基礎模型","2026-10-26 完成四市場五種模型更新","持續監控跨期表現"),
    @("USDT 利率預測","fUST 正式輸出，最佳 R² 0.8938","已重新建模與驗證"),
    @("成交機率","目前使用公開市場代理","私人可比事件至少 30 筆後校正"),
    @("策略穩定性","已完成正式 walk-forward；未勝過 FRR","後續以滾動視窗持續監控")
) @(4.1,5.4,5.8) | Out-Null

Add-Heading "完成成果與限制" 2 | Out-Null
Add-Heading "已完成成果" 2 | Out-Null
Add-Bullets @(
    "公開資料收集、GitHub Actions、本機背景排程與每日分檔。",
    "私人帳戶唯讀收集器、最低權限驗證與本機保存。",
    "特徵工程、五種模型訓練與推論、MAE／RMSE／R² 評估。",
    "基礎回測與決策報告、模型預測圖。",
    "USDT 最佳化策略比較管線、每日 10 點分析排程與唯讀 Dashboard。",
    "374 項離線自動測試通過；另有 1 項真實 API 整合測試因預設離線而未執行。"
)
Add-Heading "目前限制" 2 | Out-Null
Add-Bullets @(
    "公開市場成交代理無法完全反映本人掛單的實際佇列順位。",
    "USDT 雖已達正式資料門檻，公開成交代理仍不能取代本人真實成交與佇列資料。",
    "目前未建置幣價漲跌預測，也未考慮滑價、市場中斷與所有例外狀況。",
    "fUSD 與 fUST 的市場行為不可互相替代，只能在顯示金額時說明 USD 與 USDT 的換算假設。",
    "系統不保證收益，所有實際掛單仍需由使用者人工確認。"
)

Add-Paragraph "本專案已完成可重建、可比較、可檢視的決策輔助流程，USDT 公開資料也已通過 60 天門檻並完成正式 walk-forward 驗證。現階段最重要的分析結果是：四市場皆由前一期基準取得最佳 R²；含預測與未含預測的最佳化策略仍未勝過 FRR。因此系統已可結案驗收，但不應把模型輸出解讀為保證收益。" | Out-Null

Page-Break
Add-Heading "四 未來可擴充項" 1 | Out-Null
Add-Bullets @(
    "以 90 天、180 天及滾動視窗持續更新模型與 walk-forward 驗證，觀察結果能否跨市場情境維持。",
    "持續累積私人唯讀成交事件，以本人實際成交與等待資料校正公開市場代理。",
    "定期比較前一期基準、線性模型、決策樹與 XGBoost，僅保留跨期表現穩定的模型。",
    "把模型重建、最佳化策略與 Dashboard 串接成同一個可重複執行流程。",
    "未來可增加異常告警、資料品質監控與多資產資金配置，但仍維持人工下單安全邊界。"
)

Add-Heading "附錄 執行與查核方式" 1 | Out-Null
Add-Table @("目的","指令或檔案") @(
    @("執行離線測試","python -m pytest -q"),
    @("完整重建模型與策略","scripts/run-final-refresh.ps1"),
    @("執行最佳化策略管線","python -m bitfinex_lending.p0_strategy_pipeline"),
    @("開啟最新 Dashboard","data/modeling/p0_strategy/latest/dashboard.html"),
    @("查看模型評估","data/modeling/model_evaluations.csv"),
    @("查看最佳化策略結果","data/modeling/p0_strategy/latest/strategy_results.csv"),
    @("查看專案進度","progress.md、todo.md、PROJECT_STATUS_SUMMARY.md")
) @(5.0,11.0) | Out-Null

# Footer and page numbers
foreach($section in $doc.Sections) {
    $footer=$section.Footers.Item(1).Range
    $footer.Text="Bitfinex 放貸決策輔助系統  結案報告最終版    "
    Set-RunFont $footer 8 $false 8421504
    $footer.ParagraphFormat.Alignment=2
    $pageFieldRange=$footer.Paragraphs.Item(1).Range.Duplicate
    $pageFieldRange.End=$pageFieldRange.End-1
    $pageFieldRange.Collapse(0)
    $pageFieldRange.Fields.Add($pageFieldRange,-1,"PAGE",$true) | Out-Null
}

$doc.Fields.Update() | Out-Null
$doc.SaveAs2($OutputPath,16)
if (-not [string]::IsNullOrWhiteSpace($PdfOutputPath)) {
    $doc.ExportAsFixedFormat($PdfOutputPath,17)
}
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

Write-Output $OutputPath
if (-not [string]::IsNullOrWhiteSpace($PdfOutputPath)) { Write-Output $PdfOutputPath }
