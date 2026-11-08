param(
    [string]$OutputPath = "",
    [string]$RenderDir = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $root "deliverables\Bitfinex_放貸決策輔助系統_結案成果簡報.pptx" }
if (-not $RenderDir) { $RenderDir = Join-Path $root "deliverables\.ppt_build\rendered" }
$assets = Join-Path $root "deliverables\report_assets"

New-Item -ItemType Directory -Force (Split-Path -Parent $OutputPath) | Out-Null
New-Item -ItemType Directory -Force $RenderDir | Out-Null
Get-ChildItem -LiteralPath $RenderDir -Filter "slide-*.png" -ErrorAction SilentlyContinue | Remove-Item -Force

function C([int]$r, [int]$g, [int]$b) { return $r + 256 * $g + 65536 * $b }
$navy = C 11 27 43
$navy2 = C 23 54 93
$blue = C 36 87 130
$cyan = C 61 214 165
$orange = C 240 124 43
$ink = C 32 47 62
$muted = C 94 111 128
$light = C 242 246 249
$line = C 214 224 232
$white = C 255 255 255
$red = C 202 70 70
$font = "Microsoft JhengHei"

function Add-Rect($slide, [double]$x, [double]$y, [double]$w, [double]$h, [int]$fill, [int]$stroke = -1, [double]$radius = 0) {
    $type = if ($radius -gt 0) { 5 } else { 1 }
    $s = $slide.Shapes.AddShape($type, $x, $y, $w, $h)
    $s.Fill.ForeColor.RGB = $fill
    $s.Fill.Transparency = 0
    if ($stroke -lt 0) { $s.Line.Visible = 0 } else { $s.Line.Visible = -1; $s.Line.ForeColor.RGB = $stroke; $s.Line.Weight = 1 }
    return $s
}

function Add-Line($slide, [double]$x1, [double]$y1, [double]$x2, [double]$y2, [int]$color, [double]$weight = 1) {
    $s = $slide.Shapes.AddLine($x1, $y1, $x2, $y2)
    $s.Line.ForeColor.RGB = $color
    $s.Line.Weight = $weight
    return $s
}

function Add-Text($slide, [string]$text, [double]$x, [double]$y, [double]$w, [double]$h,
                  [double]$size = 20, [int]$color = 0, [bool]$bold = $false,
                  [int]$align = 1, [int]$valign = 1, [double]$margin = 0) {
    $s = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
    $s.Line.Visible = 0
    $s.Fill.Visible = 0
    $s.TextFrame.MarginLeft = $margin
    $s.TextFrame.MarginRight = $margin
    $s.TextFrame.MarginTop = $margin
    $s.TextFrame.MarginBottom = $margin
    $s.TextFrame.WordWrap = -1
    $s.TextFrame.VerticalAnchor = $valign
    $r = $s.TextFrame.TextRange
    $r.Text = $text
    $r.Font.Name = $font
    try { $r.Font.NameFarEast = $font } catch {}
    $r.Font.Size = $size
    $r.Font.Color.RGB = $color
    $r.Font.Bold = if ($bold) { -1 } else { 0 }
    $r.ParagraphFormat.Alignment = $align
    return $s
}

function Add-PictureFit($slide, [string]$path, [double]$x, [double]$y, [double]$w, [double]$h) {
    $img = [System.Drawing.Image]::FromFile($path)
    try {
        $ratio = $img.Width / $img.Height
        if (($w / $h) -gt $ratio) {
            $ph = $h; $pw = $h * $ratio; $px = $x + ($w - $pw) / 2; $py = $y
        } else {
            $pw = $w; $ph = $w / $ratio; $px = $x; $py = $y + ($h - $ph) / 2
        }
    } finally { $img.Dispose() }
    return $slide.Shapes.AddPicture($path, 0, -1, $px, $py, $pw, $ph)
}

function Add-Title($slide, [string]$title, [string]$kicker = "") {
    if ($kicker) { Add-Text $slide $kicker 54 25 850 18 10 $orange $true | Out-Null }
    Add-Text $slide $title 54 46 850 48 28 $ink $true | Out-Null
    Add-Rect $slide 54 98 56 4 $orange | Out-Null
}

function Add-Footer($slide, [int]$number, [bool]$dark = $false) {
    $c = if ($dark) { C 164 184 200 } else { $muted }
    $footerLine = if ($dark) { C 50 75 96 } else { $line }
    Add-Line $slide 54 508 906 508 $footerLine 0.75 | Out-Null
    Add-Text $slide "Bitfinex 放貸決策輔助系統" 54 514 400 14 8 $c $false | Out-Null
    Add-Text $slide ($number.ToString("00")) 850 514 56 14 8 $c $true 3 | Out-Null
}

function Add-BulletList($slide, [string[]]$items, [double]$x, [double]$y, [double]$w, [double]$rowH, [double]$size = 18, [int]$color = 0, [int]$dotColor = 0) {
    for ($i = 0; $i -lt $items.Count; $i++) {
        Add-Rect $slide $x ($y + $i * $rowH + 7) 8 8 $dotColor 0 4 | Out-Null
        Add-Text $slide $items[$i] ($x + 22) ($y + $i * $rowH) ($w - 22) ($rowH - 3) $size $color | Out-Null
    }
}

function Add-Table($slide, [string[][]]$data, [double]$x, [double]$y, [double]$w, [double]$h, [double[]]$ratios) {
    $rows = $data.Count; $cols = $data[0].Count
    $shape = $slide.Shapes.AddTable($rows, $cols, $x, $y, $w, $h)
    $table = $shape.Table
    for ($cidx = 1; $cidx -le $cols; $cidx++) { $table.Columns.Item($cidx).Width = $w * $ratios[$cidx - 1] }
    for ($ridx = 1; $ridx -le $rows; $ridx++) {
        for ($cidx = 1; $cidx -le $cols; $cidx++) {
            $cell = $table.Cell($ridx, $cidx).Shape
            $cell.Fill.ForeColor.RGB = if ($ridx -eq 1) { $navy2 } elseif ($ridx % 2 -eq 0) { $white } else { $light }
            $cell.TextFrame.MarginLeft = 7; $cell.TextFrame.MarginRight = 7; $cell.TextFrame.MarginTop = 4; $cell.TextFrame.MarginBottom = 3
            $tr = $cell.TextFrame.TextRange
            $tr.Text = $data[$ridx - 1][$cidx - 1]
            $tr.Font.Name = $font
            try { $tr.Font.NameFarEast = $font } catch {}
            $tr.Font.Size = if ($ridx -eq 1) { 12 } else { 13 }
            $tr.Font.Bold = if ($ridx -eq 1) { -1 } else { 0 }
            $tr.Font.Color.RGB = if ($ridx -eq 1) { $white } else { $ink }
            $tr.ParagraphFormat.Alignment = if ($cidx -eq 1) { 1 } else { 2 }
        }
    }
    return $shape
}

$ppt = $null
$pres = $null
try {
    $ppt = New-Object -ComObject PowerPoint.Application
    $ppt.Visible = -1
    $pres = $ppt.Presentations.Add()
    $pres.PageSetup.SlideWidth = 960
    $pres.PageSetup.SlideHeight = 540

    # 1. Cover
    $s = $pres.Slides.Add(1, 12)
    Add-Rect $s 0 0 960 540 $navy | Out-Null
    Add-Rect $s 58 88 8 300 $orange | Out-Null
    Add-Text $s "BITFINEX LENDING" 88 90 760 24 12 $cyan $true | Out-Null
    Add-Text $s "Bitfinex 放貸決策輔助系統" 88 132 770 66 34 $white $true | Out-Null
    Add-Text $s "結案成果簡報" 88 210 600 48 26 (C 198 218 232) $false | Out-Null
    Add-Text $s "公開資料收集、利率預測、策略比較與唯讀 Dashboard" 88 294 760 30 16 $white | Out-Null
    Add-Text $s "2026 年 10 月 21 日" 88 354 300 24 13 (C 164 184 200) | Out-Null
    Add-Text $s "研究與決策輔助用途｜不自動下單｜不構成投資建議" 88 455 710 20 11 (C 164 184 200) | Out-Null
    Add-Footer $s 1 $true

    # 2. Problem
    $s = $pres.Slides.Add(2, 12); Add-Title $s "放貸決策不是只看最高利率" "01｜問題與背景"
    Add-Text $s "高利率" 70 146 200 34 24 $navy2 $true | Out-Null
    Add-Text $s "潛在收益較高" 70 190 250 26 18 $ink | Out-Null
    Add-Text $s "但可能等待更久、增加閒置" 70 226 300 52 16 $muted | Out-Null
    Add-Rect $s 415 146 2 170 $line | Out-Null
    Add-Text $s "低利率" 468 146 200 34 24 $navy2 $true | Out-Null
    Add-Text $s "較容易快速成交" 468 190 250 26 18 $ink | Out-Null
    Add-Text $s "但可獲得的收益較低" 468 226 300 52 16 $muted | Out-Null
    Add-Rect $s 70 340 790 92 $light $line 8 | Out-Null
    Add-Text $s "核心問題" 94 360 120 24 13 $orange $true | Out-Null
    Add-Text $s "必須同時比較利率、成交機率代理、等待時間、閒置比例與淨利息。" 94 390 725 28 19 $ink $true | Out-Null
    Add-Footer $s 2

    # 3. Goals
    $s = $pres.Slides.Add(3, 12); Add-Title $s "已完成端到端決策輔助流程" "02｜目標與完成範圍"
    $labels = @("資料", "模型", "策略", "呈現")
    $heads = @("公開市場資料", "次小時利率預測", "最佳化策略", "唯讀 Dashboard")
    $descs = @("排程收集、保存與品質檢查", "時間切分、五類模型與統一指標", "收益、成交、等待與閒置同時比較", "調整本金與條件，查看結果")
    for ($i=0; $i -lt 4; $i++) {
        $x = 54 + $i * 218
        Add-Text $s $labels[$i] $x 150 185 18 11 $orange $true | Out-Null
        Add-Text $s $heads[$i] $x 181 185 56 20 $navy2 $true | Out-Null
        Add-Text $s $descs[$i] $x 250 185 85 14 $muted | Out-Null
        Add-Line $s $x 354 ($x+185) 354 $line 2 | Out-Null
    }
    Add-Text $s "系統定位" 54 397 120 22 12 $orange $true | Out-Null
    Add-Text $s "提供可追溯的比較依據；不保存交易金鑰，也不執行自動下單。" 170 392 700 34 19 $ink $true | Out-Null
    Add-Footer $s 3

    # 4. System flow
    $s = $pres.Slides.Add(4, 12); Add-Title $s "系統與資料流程" "03｜架構"
    Add-PictureFit $s (Join-Path $assets "system_flow.png") 64 126 832 315 | Out-Null
    Add-Text $s "從公開資料收集到模型、策略結果與 Dashboard，流程可重建且保留來源。" 100 458 760 28 15 $muted $false 2 | Out-Null
    Add-Footer $s 4

    # 5. Data
    $s = $pres.Slides.Add(5, 12); Add-Title $s "資料管線已能持續運作" "04｜資料收集成果"
    Add-Text $s "58.5" 62 136 200 84 52 $navy2 $true | Out-Null
    Add-Text $s "天" 205 168 50 32 20 $orange $true | Out-Null
    Add-Text $s "USDT 公開歷史約數" 64 222 240 24 14 $muted | Out-Null
    Add-Text $s "1,400" 348 136 220 84 52 $navy2 $true | Out-Null
    Add-Text $s "筆" 515 168 50 32 20 $orange $true | Out-Null
    Add-Text $s "最新策略輸出" 350 222 220 24 14 $muted | Out-Null
    Add-Text $s "2" 685 136 100 84 52 $navy2 $true | Out-Null
    Add-Text $s "條有效路徑" 753 168 120 32 18 $orange $true | Out-Null
    Add-Text $s "在地公開、私人唯讀" 687 222 220 24 14 $muted | Out-Null
    Add-Line $s 62 278 894 278 $line 1 | Out-Null
    Add-BulletList $s @(
        "在地公開收集器持續累積市場資料",
        "私人帳戶資料僅留本機，採唯讀方式收集",
        "GitHub 每日建模因 Linux 相容性問題待修正"
    ) 72 310 790 48 17 $ink $cyan
    Add-Footer $s 5

    # 6. Model design
    $s = $pres.Slides.Add(6, 12); Add-Title $s "模型評估採一致規則" "05｜模型設計"
    Add-Text $s "候選模型" 64 134 240 26 14 $orange $true | Out-Null
    Add-BulletList $s @("平均值基準", "前一期基準", "線性回歸", "決策樹", "XGBoost") 68 176 300 48 17 $ink $cyan
    Add-Rect $s 404 132 2 286 $line | Out-Null
    Add-Text $s "評估方式" 454 134 240 26 14 $orange $true | Out-Null
    Add-Text $s "80 / 20" 454 180 250 62 42 $navy2 $true | Out-Null
    Add-Text $s "依時間順序切分訓練與測試" 456 245 360 28 16 $muted | Out-Null
    Add-Text $s "MAE   RMSE   R²" 454 304 360 36 23 $ink $true | Out-Null
    Add-Text $s "以相同資料切分與指標比較所有候選模型" 456 352 390 45 16 $muted | Out-Null
    Add-Text $s "fUST：1,403 筆有效資料，已完成五種候選模型評估。" 64 445 800 26 15 $cyan $true | Out-Null
    Add-Footer $s 6

    # 7. Model results
    $s = $pres.Slides.Add(7, 12); Add-Title $s "前一期基準仍是四市場最佳模型" "06｜模型結果"
    Add-Text $s "最佳模型驗證集 R²" 54 124 300 24 13 $orange $true | Out-Null
    Add-Line $s 190 158 190 390 $line 1 | Out-Null
    $modelBars = @(
        @("fBTC", 0.4387, $cyan),
        @("fETH", -0.0586, $orange),
        @("fUSD", 0.7314, $cyan),
        @("fUST", 0.5582, $cyan)
    )
    for ($i=0; $i -lt $modelBars.Count; $i++) {
        $y = 172 + $i * 54
        $label = [string]$modelBars[$i][0]
        $value = [double]$modelBars[$i][1]
        $barColor = [int]$modelBars[$i][2]
        Add-Text $s $label 54 ($y-2) 70 24 13 $ink $true | Out-Null
        if ($value -ge 0) {
            $barWidth = 300 * $value / 0.8
            Add-Rect $s 190 $y $barWidth 24 $barColor | Out-Null
            Add-Text $s ($value.ToString("0.0000")) (198+$barWidth) ($y-2) 72 24 12 $ink $true | Out-Null
        } else {
            $barWidth = 260 * [Math]::Abs($value) / 0.8
            Add-Rect $s (190-$barWidth) $y $barWidth 24 $barColor | Out-Null
            Add-Text $s ($value.ToString("0.0000")) 112 ($y-2) 72 24 12 $ink $true 3 | Out-Null
        }
    }
    Add-Text $s "0" 181 398 20 18 10 $muted | Out-Null
    Add-Text $s "0.8" 476 398 36 18 10 $muted | Out-Null
    $modelData = [string[][]]@(
        [string[]]@("市場", "最佳模型", "R²", "有效資料"),
        [string[]]@("fBTC", "前一期基準", "0.4387", "1,584"),
        [string[]]@("fETH", "前一期基準", "-0.0586", "1,584"),
        [string[]]@("fUSD", "前一期基準", "0.7314", "1,584"),
        [string[]]@("fUST", "前一期基準", "0.5582", "1,403")
    )
    Add-Table $s $modelData 558 145 346 242 @(0.20,0.36,0.19,0.25) | Out-Null
    Add-Text $s "關鍵發現" 560 405 120 20 12 $orange $true | Out-Null
    Add-Text $s "較複雜模型尚未帶來穩定增益；現階段應優先採可解釋的前一期基準。" 560 432 332 48 15 $ink $true | Out-Null
    Add-Footer $s 7

    # 8. Strategy
    $s = $pres.Slides.Add(8, 12); Add-Title $s "最佳化策略的收益與成交取捨" "07｜策略比較"
    Add-Text $s "依模型比較不同掛單利率的成交機率、等待時間與閒置成本，選出預期淨收益最佳的策略組合。" 56 112 848 24 12 $ink | Out-Null
    Add-Text $s "範例條件：本金 1,000 USDT、名目期間 2 天、等待上限 1 小時" 56 139 840 22 11 $muted | Out-Null
    $strategyData = [string[][]]@(
        [string[]]@("策略", "成交代理", "淨利息 USDT", "期末資產", "閒置比例"),
        [string[]]@("最佳化（含預測）", "73.34%", "4.678", "1,004.678", "7.10%"),
        [string[]]@("最佳化（未含預測）", "73.34%", "4.678", "1,004.678", "7.10%"),
        [string[]]@("穩定替代", "93.73%", "3.756", "1,003.756", "6.27%"),
        [string[]]@("快速成交", "99.64%", "2.939", "1,002.939", "7.00%"),
        [string[]]@("FRR", "73.34%", "4.678", "1,004.678", "7.10%")
    )
    Add-Table $s $strategyData 56 171 848 229 @(0.24,0.18,0.21,0.21,0.16) | Out-Null
    Add-Rect $s 56 420 848 55 $light $line 5 | Out-Null
    Add-Text $s "目前快照中，含預測與未含預測的最佳化結果皆與 FRR 相同，尚未證明額外優勢。" 75 435 810 27 15 $ink $true 2 | Out-Null
    Add-Footer $s 8

    # 9. Dashboard
    $s = $pres.Slides.Add(9, 12); Add-Title $s "結果可在唯讀 Dashboard 直接檢視" "08｜成果介面"
    Add-Rect $s 46 120 650 365 $navy $navy 6 | Out-Null
    Add-PictureFit $s (Join-Path $assets "dashboard_latest.png") 52 126 638 353 | Out-Null
    Add-Text $s "可調整" 730 145 160 24 13 $orange $true | Out-Null
    Add-Text $s "本金、期限與等待條件" 730 177 170 56 17 $ink $true | Out-Null
    Add-Text $s "可查看" 730 260 160 24 13 $orange $true | Out-Null
    Add-Text $s "成交代理、等待、淨利息與期末資產" 730 292 170 80 17 $ink $true | Out-Null
    Add-Text $s "唯讀｜不含金鑰｜不送單" 730 418 170 45 14 $red $true | Out-Null
    Add-Footer $s 9

    # 10. Maturity
    $s = $pres.Slides.Add(10, 12); Add-Title $s "資料成熟度仍在正式門檻前" "09｜60 天門檻"
    Add-Text $s "58.5" 80 145 220 95 58 $navy2 $true | Out-Null
    Add-Text $s "/ 60 天" 255 185 190 42 25 $muted $true | Out-Null
    Add-Text $s "目前公開歷史" 83 242 240 26 15 $muted | Out-Null
    Add-Rect $s 82 300 760 20 (C 222 232 239) 0 8 | Out-Null
    Add-Rect $s 82 300 (760 * 58.5 / 60) 20 $cyan 0 8 | Out-Null
    Add-Text $s "experimental" 82 344 250 36 23 $orange $true | Out-Null
    Add-Text $s "現有資料足以驗證收集、模型與介面流程；尚不足以進行正式策略驗證。" 82 391 760 48 18 $ink $true | Out-Null
    Add-Footer $s 10

    # 11. Completed outcomes
    $s = $pres.Slides.Add(11, 12); Add-Title $s "可交付成果已形成完整鏈條" "10｜完成項目"
    $done = @(
        @("01", "自動收集", "公開市場排程與在地補強"),
        @("02", "模型評估", "統一時間切分與模型比較"),
        @("03", "策略輸出", "最佳化策略比較與每日 10 點排程"),
        @("04", "成果介面", "唯讀 Dashboard 與結案文件"),
        @("05", "品質檢查", "372 項離線測試通過")
    )
    for ($i=0; $i -lt $done.Count; $i++) {
        $y = 132 + $i * 68
        Add-Text $s $done[$i][0] 66 $y 58 36 21 $orange $true | Out-Null
        Add-Text $s $done[$i][1] 142 $y 190 36 19 $navy2 $true | Out-Null
        Add-Text $s $done[$i][2] 340 ($y+2) 520 34 16 $ink | Out-Null
        if ($i -lt 4) { Add-Line $s 142 ($y+48) 870 ($y+48) $line 0.75 | Out-Null }
    }
    Add-Footer $s 11

    # 12. Limitations
    $s = $pres.Slides.Add(12, 12); Add-Title $s "結論必須保留資料與方法邊界" "11｜限制與風險"
    $limits = @(
        @("成交代理", "公開市場成交代理不等於本人掛單的真實成交與佇列順位。"),
        @("資料天數", "USDT 公開歷史約 58.5 天，尚未達正式 60 天門檻。"),
        @("模型限制", "四個市場皆由前一期基準取得最佳 R²，複雜模型尚未顯示穩定增益。"),
        @("操作邊界", "系統不自動下單；使用者仍須人工確認條件與風險。"),
        @("用途聲明", "結果為研究與決策輔助，不構成投資建議。")
    )
    for ($i=0; $i -lt $limits.Count; $i++) {
        $y = 128 + $i * 69
        Add-Text $s $limits[$i][0] 62 $y 145 28 15 $orange $true | Out-Null
        Add-Text $s $limits[$i][1] 220 $y 650 44 16 $ink | Out-Null
        if ($i -lt 4) { Add-Line $s 220 ($y+51) 880 ($y+51) $line 0.75 | Out-Null }
    }
    Add-Footer $s 12

    # 13. Conclusion
    $s = $pres.Slides.Add(13, 12)
    Add-Rect $s 0 0 960 540 $navy | Out-Null
    Add-Text $s "結論" 66 52 250 30 13 $orange $true | Out-Null
    Add-Text $s "已完成可重建、可比較、可檢視的決策輔助系統" 66 103 820 80 31 $white $true | Out-Null
    Add-Text $s "目前證據" 66 217 210 24 13 $cyan $true | Out-Null
    Add-BulletList $s @(
        "前一期基準是現階段最穩定的預測方法",
        "最佳化策略尚未證明優於 FRR",
        "系統已可持續累積正式驗證所需資料"
    ) 70 253 760 48 17 $white $cyan
    Add-Line $s 66 405 890 405 (C 50 75 96) 1 | Out-Null
    Add-Text $s "下一步" 66 430 100 22 12 $orange $true | Out-Null
    Add-Text $s "達到 60 天資料門檻｜增加私人可比事件｜持續觀察模型｜執行 walk-forward 驗證" 164 426 720 36 15 $white $true | Out-Null
    Add-Text $s "所有結果仍需人工確認，不構成投資建議。" 66 478 620 18 10 (C 164 184 200) | Out-Null
    Add-Footer $s 13 $true

    if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
    $pres.SaveAs($OutputPath, 24)
    for ($i = 1; $i -le $pres.Slides.Count; $i++) {
        $renderPath = Join-Path $RenderDir ("slide-{0:D2}.png" -f $i)
        $pres.Slides.Item($i).Export($renderPath, "PNG", 1600, 900)
    }
    Write-Output "PPTX=$OutputPath"
    Write-Output "SLIDES=$($pres.Slides.Count)"
    Write-Output "RENDER_DIR=$RenderDir"
}
finally {
    if ($pres) { try { $pres.Close() } catch {} }
    if ($ppt) { try { $ppt.Quit() } catch {} }
    if ($pres) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) }
    if ($ppt) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
