# Bitfinex 放貸市場決策輔助系統待辦清單

## 2026-08-24 目前狀態與暫停後續作順序

### 已完成的安全檢查點

- [x] 將 `fUST` 納入本機 funding-book 收集與原始 CSV 寫入
- [x] 建立可操作的實驗模型與本機唯讀 Dashboard
- [x] 將公開市場成交代理標示為非常低可信度實驗值並補齊主要限制
- [x] 以 commit `14c5afa` 安全提交 10 個實驗模型／Dashboard 程式及測試檔
- [x] 完成該檢查點的獨立審查與完整離線測試（`284 passed, 1 deselected`）

### 恢復開發後的 P0 順序

- [ ] 分批審查並整理其餘未提交的正式程式、測試與文件；持續排除私人資料及 `data/` 收集結果
- [ ] 實作官方利息、15% 手續費、複利、資金閒置與市場容量規則
- [ ] 正規化 USDT 公開市場歷史資料並建立資料成熟度判定
- [ ] 估算候選利率的成交機率、等待時間與可部署金額
- [ ] 完成 1,000～10,000 USDT 拆單及最高收益／較穩定替代策略
- [ ] 完成 walk-forward 與固定中位利率、FRR、低利率快速成交基準比較
- [ ] 統一 Dashboard、CSV、JSON 與 Markdown 結果及狀態標示
- [ ] 建立每日策略分析排程，失敗時保留上一個成功版本
- [ ] 完成正式 P0 全套測試、隱私檢查與 production path 驗證

### 結案報告與資料成熟度

- [ ] 先以實驗結果整理結案報告，明確說明資料不足、成交代理限制及不自動下單
- [ ] 公開 USDT 資料達正式門檻後，以正式回測數字更新報告
- [ ] 持續觀察 60 天、每小時完整率至少 90%、最大缺口不超過 6 小時及每策略至少 30 次驗證機會

### 暫緩項目

- [ ] P1 GitHub 輔助收集策略
- [ ] P1 本機與 GitHub 兩來源衝突檢查及合併規則

> 目前先停在此檢查點處理其他事項；本機公開與私人收集排程維持運作，未取得新指示前不繼續上述實作。

## 2026-08-16 最小本機穩定收集器

- [x] 重用既有 public API client、SQLite storage 與 CSV exporter
- [x] 建立每市場有限次數重試
- [x] 建立單次執行 lock
- [x] 保存本機成功／失敗摘要日誌
- [x] 建立本機 CLI 與操作文件
- [x] 建立並啟用 Windows 每小時排程
- [x] 收集公開 ticker、funding statistics、funding candles 與價格資料
- [x] 將公開 market 資料分開保存於 `data/market/`
- [x] 將公開 market 與私人 account CSV 統一改為 UTC 每日分檔
- [x] 將 2026-08-16 起舊單檔安全分割歸檔並完成逐列核對
- [x] 觀察實際本機連續收集結果
- [ ] 另行設計 GitHub 輔助收集策略
- [ ] 另行設計兩來源資料衝突檢查與合併規則

## 2026-08-16 策略最佳化新目標

- [x] 建立 `strategy_optimization_goals.md`
- [x] 完成 P0 新版需求訪談與正式設計（權威規格見 [`docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md`](docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md)）
- [x] 依新版設計修訂 P0 實作計畫與執行清單（[`實作計畫`](docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md)；[`執行清單`](docs/P0_EXECUTION_CHECKLIST.md)）
- [ ] 完成 1,000～10,000 USDT 十組本金、每份 1,000 USDT 的拆單收益比較
- [ ] 完成 2／5／10／30 天與 1／3／6／12／24 小時等待策略比較
- [ ] 實作官方按秒計息、15% 手續費、複利、資金閒置與市場容量限制
- [x] 建立歷史掛單／成交／取消資料格式
- [ ] 建立成交機率模型
- [ ] 將成交機率接入策略預期收益計算
- [ ] 完成 walk-forward 與固定中位利率／FRR／低利率快速成交三種基準比較
- [ ] 比較有／無原利率預測模型的策略結果
- [ ] 輸出最高收益策略與較穩定替代策略
- [ ] 完成策略最佳化 CSV／Markdown 報告與本機唯讀互動介面
- [ ] 建立每日台灣時間 10:00 更新及失敗保留上一版結果的機制
- [ ] 完成策略最佳化測試、隱私保護與限制說明
- [ ] 公開 USDT 資料達正式門檻：連續 60 天、每小時完整率至少 90%、最長缺口不超過 6 小時、每種策略至少 30 次驗證機會

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

> 狀態界線：以上僅為結案呈現方式的**測試版／技術驗證版**。正式結案報告、正式結案簡報及正式結案影片均尚未開始製作。

### 正式結案報告（尚未開始）

- [ ] 確認正式結案報告格式、繳交規範、篇幅與截止日期
- [ ] 建立正式結案報告大綱與章節責任清單
- [ ] 整理問題定義、系統架構、資料流程與實作方法
- [ ] 更新最終資料量、GitHub Actions 執行證據與資料品質結果
- [ ] 整理達門檻後的真實模型評估與圖表；若仍未達門檻，明確說明限制
- [ ] 完成回測與業務指標，或在範圍調整後說明未納入原因
- [ ] 撰寫研究限制、風險、人工確認及不自動下單聲明
- [ ] 完成正式結案報告初稿
- [ ] 校對引用、圖表、數字與程式輸出的一致性
- [ ] 依正式報告內容製作結案簡報／影片（若繳交規範需要）

### 下次開始時先做

- [ ] 同步 `origin/master` 並檢查近期自動收集 commits
- [ ] 檢查每日 `18:37 UTC` scheduled modeling workflow，補登 run ID 與結果
- [ ] 重建 modeling outputs，記錄各市場最新 features／有效資料筆數
- [ ] 任一市場達 168 筆後，驗證第一階段模型實際評估與預測輸出
- [ ] 根據最新資料狀態更新 `progress.md` 與本清單

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
- [ ] 觀察至少一次每日 scheduled modeling run
- [ ] 任一市場達 168 筆有效資料後，確認三個第一階段模型產生評估與預測

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
- [ ] 訓練決策樹模型
- [ ] 訓練 XGBoost 模型
- [x] 輸出 MAE
- [x] 輸出 RMSE
- [x] 輸出 R2
- [x] 建立模型比較表
- [x] 建立決策樹模型
- [x] 建立 XGBoost 模型
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
- [ ] 撰寫回測結果解讀

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
- [ ] 撰寫建模流程說明
- [ ] 撰寫模型效能評估報告
- [ ] 撰寫回測與業務指標報告
- [ ] 撰寫使用限制與人工確認流程
- [ ] 製作 Demo 簡報
- [ ] Demo 簡報包含欄位定義
- [ ] Demo 簡報包含資料來源
- [ ] Demo 簡報包含應用情境
- [ ] Demo 簡報包含使用限制

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
- [ ] 可輸出建議觀察利率區間
- [x] 可顯示風險與使用限制
- [x] 所有建議明確標示需人工確認
- [x] 系統不自動下單
- [x] 可輸出建議觀察利率區間
- [ ] 文件足以讓使用者安裝、執行、訓練模型、執行回測與查看結果
## 私有 Funding 唯讀收集器

- [x] 使用本機唯讀憑證完成一次 `--dry-run`
- [x] 使用本機唯讀憑證完成一次手動收集
- [x] 使用排程腳本預覽並確認設定
- [x] 使用者明確同意後才啟用 Windows 排程
- [x] 觀察排程至少 24 小時並確認無 nonce/權限錯誤
