# Bitfinex 放貸市場決策輔助系統待辦清單

## 2026-08-30 專案整理與目前續作入口

- [x] 盤點 54 組尚未整理的程式、測試、文件、模型產出及資料目錄
- [x] 確認私人 `data/account/`、憑證與私人狀態檔持續由 Git 永久排除
- [x] 盤點 7 個舊 worktree，移除 5 個不影響 P0／P1 的重複工作目錄並保留分支
- [x] 統一 `progress.md`、本清單、P0 執行清單、P0 進度快照與最終成果說明
- [x] 完成 USDT-only Dashboard 2.1，並修正四種期限各自的快速成交與中位利率基準
- [x] 將 257 個最新本機公開資料檔安全同步至 GitHub `master`（commit `9fb64a1`）
- [x] 分批審查並提交正式模型／回測／決策輔助與最佳化策略流程及測試（安全分支 checkpoints `df4a081`、`6ff5a57`）
- [x] 決定 Git 保存規則並產生最新成果：保存正式模型／策略輸出；公開原始資料由同步管線管理；私人資料、執行狀態與大型交付檔不提交
- [x] 整理正式結案報告大綱、繳交規範、可用圖表與影片素材
  - [x] 已確認目前無固定繳交範本，並建立 [`docs/FINAL_REPORT_OUTLINE.md`](docs/FINAL_REPORT_OUTLINE.md) 作為正式章節與完成標準
  - [x] 依大綱盤點可用圖表、Dashboard 截圖與影片素材

> 功能與準備版報告均已完成；最新正式重建數字以 2026-10-26 為準，60 天資料門檻與正式 walk-forward 已完成，最終報告輸出依使用者指示延後處理。

## 2026-10-26 每日完整更新

- [x] 確認原每日 10:00 排程只更新最佳化策略與 Dashboard，未先重建本機模型
- [x] 以測試先行方式將排程入口改為 `scripts/run-final-refresh.ps1`
- [x] 保留原工作名稱、每日 10:00、隱藏執行、`IgnoreNew`、`StartWhenAvailable` 與 30 分鐘上限
- [x] 更新既有 Windows 排程並手動觸發一次完整驗收（2026-10-26 11:14，`LastTaskResult=0`）

## 2026-10-26 公開資料同步失敗診斷

- [x] 以測試先行補上失敗階段、Git 回傳碼與實際推送嘗試次數
- [x] 確認狀態檔不保存完整命令、遠端網址或錯誤輸出
- [x] 保留既有白名單、私人資料排除及推送重試行為

## 2026-08-24 GitHub 同步成果

- [x] 保留 GitHub Actions `data/raw/`，將本機公開資料分流至 `data/local_public/`
- [x] 核對並同步 2026-08-16 起的本機 raw、ticker、stats、candles 與 prices 公開資料
- [x] 同步公開／私人收集器程式、排程、測試與操作文件，但永久排除私人資料
- [x] 同步實驗模型、Dashboard、`progress.md`、`todo.md` 與直接關聯文件
- [x] 修正並實際驗證 `fUST` funding-book 每日 CSV 寫入
- [x] 建立每週一 10:00 自動同步、關機後補跑、無變更不建立空提交
- [x] 完成遠端白名單、私人資料排除與完整離線測試驗證
- [x] 完成 GitHub 與本機兩來源的衝突檢查、去重與模型層合併規則（本機同小時優先、GitHub 補缺）

> 本次久未同步的臨時作業已完成；長期操作方式見 `docs/PUBLIC_GITHUB_SYNC.md`。公開與私人收集排程維持運作，後續回到 P0 策略模型與結案報告主線。

## 2026-08-24 目前狀態與暫停後續作順序

### 已完成的安全檢查點

- [x] 將 `fUST` 納入本機 funding-book 收集與原始 CSV 寫入
- [x] 建立可操作的實驗模型與本機唯讀 Dashboard
- [x] 將公開市場成交代理標示為非常低可信度實驗值並補齊主要限制
- [x] 以 commit `14c5afa` 安全提交 10 個實驗模型／Dashboard 程式及測試檔
- [x] 完成該檢查點的獨立審查與完整離線測試（`284 passed, 1 deselected`）

### 恢復開發後的 P0 順序

- [ ] 分批審查並整理其餘未提交的正式程式、測試與文件；持續排除私人資料及 `data/` 收集結果
- [x] 實作官方按秒利息、15% 手續費與 1,000 單位資金網格（P0 Task 2）
- [x] 正規化 USDT 公開市場歷史資料並建立資料成熟度判定（P0 Task 3）
- [x] 估算候選利率的成交機率、等待時間與可部署金額（P0 Task 4）
- [x] 完成複利、資金閒置、市場容量與 1,000～10,000 USDT 拆單的最高收益／較穩定替代策略（P0 Task 5）
- [x] 完成 walk-forward 與固定中位利率、FRR、低利率快速成交基準比較（P0 Task 6）
- [x] 統一 CSV、JSON、Markdown 與狀態輸出，並建立原子發布、隱私阻擋及 last-good 保護（P0 Task 7）
- [x] 將 Task 7 統一結果接入正式本機唯讀 Dashboard（P0 Task 8）
- [x] 建立每日策略分析管線及台灣時間 10:00 排程，失敗時保留上一個成功版本（P0 Task 9）
  - [x] Task 9A：完成手動分析管線、原子輸出、last-good 與實際本機資料驗證
  - [x] Task 9B：完成 preview-first 排程腳本、操作文件、每日排程註冊與手動觸發驗收
- [x] 完成正式 P0 全套測試、隱私檢查與 production path 驗證（2026-10-12；`367 passed, 1 deselected`；跨格式一致；敏感詞無命中）

### 結案報告與資料成熟度

- [x] 先以實驗結果整理結案報告，明確說明資料不足、成交代理限制及不自動下單
- [ ] 公開 USDT 資料達正式門檻後，以正式回測數字更新報告
- [x] 持續觀察 60 天、每小時完整率至少 90%、最大缺口不超過 6 小時及每策略至少 30 次驗證機會（2026-10-26：62.96 天、100%、1 小時、至少 1,489 次）

### 暫緩項目

- [x] P1 GitHub 輔助收集策略（改為每週同步獨立的 `data/local_public/`）
- [x] P1 本機與 GitHub 兩來源衝突檢查及合併規則（2026-10-26 完成模型層合併與真實資料驗收）

> 此段原為暫停檢查點；GitHub 公開資料分流與同步已於同日完成，其餘 P0 項目仍依上列順序續作。

## 2026-08-16 最小本機穩定收集器

- [x] 重用既有 public API client、SQLite storage 與 CSV exporter
- [x] 建立每市場有限次數重試
- [x] 建立單次執行 lock
- [x] 保存本機成功／失敗摘要日誌
- [x] 建立本機 CLI 與操作文件
- [x] 建立並啟用 Windows 每小時排程
- [x] 收集公開 ticker、funding statistics、funding candles 與價格資料
- [x] 將本機公開 market 資料分開保存於 `data/local_public/market/`
- [x] 將公開 market 與私人 account CSV 統一改為 UTC 每日分檔
- [x] 將 2026-08-16 起舊單檔安全分割歸檔並完成逐列核對
- [x] 觀察實際本機連續收集結果
- [x] 建立每週 GitHub 輔助同步策略，且不影響每小時本機收集
- [x] 完成兩來源資料衝突檢查與合併規則（本機同小時優先、GitHub 補缺）

## 2026-08-16 策略最佳化新目標

- [x] 建立 `strategy_optimization_goals.md`
- [x] 完成 P0 新版需求訪談與正式設計（權威規格見 [`docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md`](docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md)）
- [x] 依新版設計修訂 P0 實作計畫與執行清單（[`實作計畫`](docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md)；[`執行清單`](docs/P0_EXECUTION_CHECKLIST.md)）
- [x] 完成 1,000～10,000 USDT 十組本金、每份 1,000 USDT 的拆單收益比較
- [x] 完成 2／5／10／30 天與 1／3／6／12／24 小時等待策略比較
- [x] 實作官方按秒計息、15% 手續費、複利、資金閒置與市場容量限制
- [x] 建立歷史掛單／成交／取消資料格式
- [x] 建立公開市場成交機率代理模型（正式校正仍待私人可比事件）
- [x] 將成交機率代理接入策略預期收益計算
- [x] 完成 walk-forward 程式及固定中位利率／FRR／低利率快速成交三種基準比較（正式執行仍待 60 天）
- [x] 比較有／無原利率預測模型的策略結果
- [x] 輸出最高收益策略與較穩定替代策略
- [x] 完成策略最佳化 CSV／Markdown 報告與本機唯讀互動介面
- [x] 建立每日台灣時間 10:00 更新及失敗保留上一版結果的機制
- [x] 完成策略最佳化測試、隱私保護與限制說明
- [x] 公開 USDT 資料達正式門檻：連續 60 天、每小時完整率至少 90%、最長缺口不超過 6 小時、每種策略至少 30 次驗證機會（2026-10-26 達成）

> P0 目前已完成生命週期表、掛單／成交配對稽核、B1／B2 基準定義及新版產品設計。程式可在資料累積期間先行實作；未達 60 天公開資料門檻時，結果只能標示為實驗版。詳細需求以新版權威規格為準。

## 2026-07-29 續作優先順序

### 結案測試影片

- [x] 完成 25 秒、1920×1080 的系統架構與資料流測試影片
- [x] 呈現 funding-book → GitHub Actions → Raw CSV／SQLite → 特徵工程 → 模型門檻
- [x] 使用已驗證的 `80 / 168` 與 `insufficient_data`，不虛構模型或收益結果
- [x] 完成 5.5、17、24、24.25 秒 proof snapshots 與人工畫面檢查
- [x] 通過 HyperFrames 0.7.78 完整檢查（0 errors；contrast 59/59）
- [x] 產出 25 秒、1920×1080、H.264 MP4 測試成品
- [ ] 決定是否將 `feature/bitfinex-system-flow-motion` 合併回 `master`

> 狀態界線：以上僅為結案呈現方式的**測試版／技術驗證版**。正式結案報告已建立章節大綱，正文、正式簡報及正式影片尚未開始製作。

### 正式結案報告（PDF 準備版已完成）

- [x] 確認目前沒有固定格式、篇幅與截止日期；後續若收到規範再調整排版
- [x] 建立正式結案報告大綱與章節完成標準：[`docs/FINAL_REPORT_OUTLINE.md`](docs/FINAL_REPORT_OUTLINE.md)
- [x] 整理問題定義、系統架構、資料流程與實作方法
- [x] 更新準備版資料量、GitHub Actions 執行證據與資料品質結果
- [x] 整理目前模型評估與圖表，並明確說明尚未達正式門檻
- [x] 整理實驗性回測與業務指標；正式數字保留至 60 天後更新
- [x] 撰寫研究限制、風險、人工確認及不自動下單聲明
- [x] 完成正式結案報告準備版
- [x] 校對準備版圖表、數字與程式輸出的一致性
- [x] 依正式報告內容製作 13 頁結案成果簡報（不搭配口頭講述）

### 結案成果簡報

- [x] 確認簡報為不搭配口頭講述的獨立成果展示
- [x] 確認採 12～14 頁成果版架構並刪減技術附錄內容
- [x] 盤點並凍結簡報使用的最新圖表與數字（2026-10-15；USDT 約 52 天、策略輸出 1,000 筆）
- [x] 建立 13 頁 PPTX
- [x] 渲染全部投影片並檢查文字溢出與圖表可讀性
- [x] 逐頁檢查後未發現需局部修正的版面問題
- [x] 交付 PPTX 供使用者審閱
- [x] 將簡報中的「P0 策略」統一改稱「最佳化策略」，並補充簡單判斷條件與基準
- [x] 依最新本機資料修正 fUST 狀態說明，不再誤寫為資料不足
- [x] 重新產生 13 頁 PPTX，逐頁檢查修改頁與其餘頁面

### 2026-10-21 最新資料重建

- [x] 稽核 GitHub Actions 與四個本機 Windows 排程
- [x] 以 `data/local_public/raw` 建立候選模型並驗證 fUST
- [x] 使用最新本機資料重建正式模型輸出
- [x] 重新產生最佳化策略與唯讀 Dashboard
- [x] 依新模型與 Dashboard 更新結案簡報
- [x] 修正 GitHub 每日建模的 Linux／Windows 測試相容性並完成遠端驗收（run `39687079671`）

### 下次開始時先做

- [x] 同步 `origin/master` 並檢查近期自動收集 commits
- [x] 檢查每日 `18:37 UTC` scheduled modeling workflow，補登 run ID 與結果
- [x] 重建 modeling outputs，記錄各市場最新 features／有效資料筆數
- [x] 任一市場達 168 筆後，驗證第一階段模型實際評估與預測輸出
- [x] 根據最新資料狀態更新 `progress.md` 與本清單
- [x] 修正 GitHub Actions 在 Linux 匯入 Windows-only `msvcrt` 的測試收集錯誤，提交並完成 Ubuntu 遠端驗收

### 2026-10-21 PDF 結案報告與 60 天門檻

- [x] 建立跨平台檔案鎖，修正 GitHub Actions 的 Linux 測試收集錯誤
- [x] 本機執行跨平台鎖定測試、完整測試與模型建置驗證
- [x] 準備 60 天達標後的模型、策略與 Dashboard 重建流程
- [x] 先完成 PDF 結案報告的分析目的與分析方法，並輸出逐頁 PNG 完成版面檢查
- [ ] 達到 60 天後更新分析結果
- [x] 完成準備版的未來可擴充項
- [ ] 達到 60 天後輸出並逐頁檢查最終 PDF

## 2026-07-21 自動特徵工程與建模

- [x] 完成嚴格 Repository 原始 CSV 載入器與驗證矩陣
- [x] 確認中斷成果保存在 `feature/automated-feature-modeling` worktree
- [x] 執行功能分支基準測試（94 passed, 1 deselected）
- [x] 完成 168 筆門檻、時序切分、兩個 baseline 與線性迴歸
- [x] 完成 model status／evaluation／prediction 固定格式 CSV
- [x] 完成 `python -m bitfinex_lending.modeling` 建模命令
- [x] 完成每日 18:37 UTC GitHub Actions 建模 workflow
- [x] 執行本地 production path 與完整離線驗收（110 passed, 1 deselected）
- [x] 確認目前三市場資料不足時輸出 `insufficient_data`，不產生誤導性模型結果
- [x] 將功能分支整合並推送至 GitHub
- [x] 手動執行一次 Build Bitfinex modeling dataset workflow
- [x] 觀察至少一次每日 scheduled modeling run（2026-10-25 成功，run `40234085591`）
- [x] 任一市場達 168 筆有效資料後，確認第一階段模型產生評估與預測（目前四市場皆已產出）

## 2026-07-21 GitHub Actions 自動收集

- [x] 建立 UTC 每日、每市場 CSV 追加輸出
- [x] 建立同一 run ID 去重與原子檔案更新
- [x] 建立每小時第 17 分鐘 GitHub Actions 排程
- [x] 建立 workflow 手動執行入口
- [x] 建立成功資料自動 commit 與 push
- [x] 建立部分失敗仍保存成功市場資料的流程
- [x] 在 GitHub private repository 啟用 workflow 寫入權限
- [x] 從 GitHub Actions 手動執行並確認自動 commit
- [x] 觀察至少一次 scheduled run

## 2026-07-14 特徵工程完成項目

- [x] 建立 SQLite `modeling_features` 資料表
- [x] 建立市場、時間、利率、數量、期間、供需與差分特徵欄位
- [x] 建立下一期加權平均利率目標欄位
- [x] 輸出 `modeling_features.csv`
- [x] 建立 `python -m bitfinex_lending.features` 批次重建指令

## 需求與設計

- [x] 閱讀原始專案企劃書
- [x] 收斂第一版資料收集需求
- [x] 建立第一版 `prd.md`
- [x] 建立新版現實可用企劃書
- [x] 更新 `prd.md` 為決策輔助系統版本
- [x] 設計整體資料流程
- [x] 設計 SQLite schema
- [x] 決定 CSV 輸出格式
- [x] 定義建模資料集格式
- [x] 定義 baseline 策略
- [x] 定義模型策略輸出格式
- [x] 定義回測規則
- [x] 定義決策輔助輸出格式

## API 探索

- [x] 確認 Bitfinex funding book API endpoint
- [x] 測試 `fUSD` 單次抓取
- [x] 測試 `fBTC` 單次抓取
- [x] 測試 `fETH` 單次抓取
- [x] 確認 API 回傳欄位意義
- [x] 確認 `rate`、`period`、`count`、`amount` 解析方式
- [x] 確認 `amount` 正負值與 `side` 的對應規則
- [x] 確認 API 錯誤或空資料時的回應格式

## 資料收集程式

- [x] 建立 Python 專案結構
- [x] 建立設定檔或常數管理 markets
- [x] 實作 Bitfinex API 請求函式
- [x] 實作三個 markets 依序抓取
- [x] 實作 funding book 快照整理
- [x] 加入請求錯誤處理
- [x] 加入執行時間戳記
- [x] 建立 crawl log
- [x] 建立 error log

## SQLite 與 CSV

- [x] 建立 SQLite 資料庫
- [x] 建立 funding book 快照資料表
- [x] 建立建模資料集資料表
- [x] 建立 crawl log 資料表
- [x] 建立 error log 資料表
- [ ] 建立模型評估結果資料表
- [ ] 建立回測結果資料表
- [x] 實作原始整理資料寫入 SQLite
- [x] 實作建模資料集輸出 CSV
- [x] 實作模型評估表輸出 CSV
- [ ] 實作回測結果表輸出 CSV

## 特徵工程

- [x] 產生 `market`
- [x] 產生 `feature_time`
- [x] 產生 `hour`
- [x] 產生 `day_of_week`
- [x] 產生 `avg_rate`
- [x] 產生 `weighted_avg_rate`
- [x] 產生 `min_rate`
- [x] 產生 `max_rate`
- [x] 產生 `total_amount`
- [x] 產生 `avg_period`
- [x] 產生 `offer_count`
- [x] 產生 `demand_count`
- [x] 產生 `rate_spread`
- [x] 產生 `previous_weighted_avg_rate`
- [x] 產生 `rate_change`
- [x] 產生 `amount_change`
- [x] 產生 `target_next_weighted_avg_rate` 預測目標欄位

## 建模

- [x] 建立訓練集與驗證集切分流程
- [x] 建立 baseline：平均值預測
- [x] 建立 baseline：前一期利率預測
- [x] 訓練線性迴歸模型
- [x] 訓練決策樹模型
- [x] 訓練 XGBoost 模型
- [x] 輸出 MAE
- [x] 輸出 RMSE
- [x] 輸出 R2
- [x] 建立模型比較表
- [x] 建立預測值與實際值比較圖（SVG）
- [x] 撰寫模型結果解讀

## 回測與業務指標

- [x] 定義 baseline 策略的回測規則
- [x] 定義模型策略的回測規則
- [x] 實作 baseline 策略回測
- [x] 實作模型策略回測
- [x] 計算模擬成交率
- [x] 計算資金利用率
- [x] 計算平均等待時間
- [x] 計算最大連續未成交時間
- [x] 計算模擬年化收益
- [x] 比較模型策略與 baseline 策略差異
- [x] 撰寫回測結果解讀

## 決策輔助輸出

- [x] 輸出建議觀察利率區間
- [x] 輸出模型預測值
- [x] 輸出模型信心或限制提示
- [x] 輸出 baseline 策略比較
- [x] 輸出模擬成交率與等待時間
- [x] 輸出風險與使用限制
- [x] 明確標示需人工確認
- [x] 確認系統不執行任何真實下單或帳戶操作

## 文件與 Demo

- [x] 撰寫操作說明
- [x] 撰寫資料來源說明
- [x] 撰寫欄位定義
- [x] 撰寫建模流程說明
- [x] 撰寫模型效能評估報告
- [x] 撰寫實驗性回測與業務指標報告
- [x] 撰寫使用限制與人工確認流程
- [x] 製作 Demo 簡報
- [x] Demo 簡報包含欄位定義
- [x] Demo 簡報包含資料來源
- [x] Demo 簡報包含應用情境
- [x] Demo 簡報包含使用限制

## 驗收

- [x] 可抓取 `fUSD`、`fBTC`、`fETH`
- [x] SQLite 成功保存原始整理資料
- [x] CSV 成功輸出建模資料集
- [x] 可建立 baseline
- [x] 可訓練線性迴歸
- [x] 可訓練決策樹
- [x] 可訓練 XGBoost
- [x] 可輸出 MAE、RMSE、R2
- [x] 可比較各模型表現
- [x] 可執行 baseline 策略回測
- [x] 可執行模型策略回測
- [x] 可計算模擬成交率
- [x] 可計算資金利用率
- [x] 可計算平均等待時間
- [x] 可輸出建議觀察利率區間
- [x] 可顯示風險與使用限制
- [x] 所有建議明確標示需人工確認
- [x] 系統不自動下單
- [ ] 文件足以讓使用者安裝、執行、訓練模型、執行回測與查看結果
## 私有 Funding 唯讀收集器

- [x] 使用本機唯讀憑證完成一次 `--dry-run`
- [x] 使用本機唯讀憑證完成一次手動收集
- [x] 使用排程腳本預覽並確認設定
- [x] 使用者明確同意後才啟用 Windows 排程
- [x] 觀察排程至少 24 小時並確認無 nonce/權限錯誤

## 結案報告 DOCX

- [x] 確認單一整合版 DOCX 的內容範圍
- [x] 盤點模型、策略、Dashboard 與可用圖表資料
- [x] 產生第一版 DOCX 並完成 9 頁逐頁檢查
- [x] 找出表格後段落插入及圖表換頁問題並準備修正
- [x] 重新產生修正版 DOCX
- [x] 逐頁檢查修正版並修正剩餘排版問題
- [x] 交付 DOCX 供使用者審閱
- [x] 使用者確認結案格式改為 PDF，已輸出並逐頁檢查準備版；最終版待 60 天後更新

續作細節見 [`docs/FINAL_REPORT_DRAFT_STATUS.md`](docs/FINAL_REPORT_DRAFT_STATUS.md)。
