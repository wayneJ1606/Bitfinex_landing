# Bitfinex 放貸市場決策輔助系統進度紀錄

## 2026-08-24 GitHub 公開資料分流與同步完成

- GitHub Actions 公開 funding-book 保留於 `data/raw/`；本機公開收集器已改寫入 `data/local_public/raw/` 與 `data/local_public/market/`，兩個來源不再共同修改同一批 CSV。
- 已將 2026-08-16～2026-08-24 的本機公開資料核對後分流；第一次 GitHub 同步共 149 個檔案、2,685,616 bytes，commit `c3329ea`，遠端 commit tree 經確認只含 `data/local_public/`。
- 舊位置的 147 個來源檔已在雜湊核對後移至本機可復原封存區 `data/archive/local-public-pre-separation-20260824/`；私人 `data/account/`、憑證、私人狀態及識別碼未同步。
- 公開／私人收集器程式、排程、測試、操作文件、實驗模型／Dashboard、`progress.md`、`todo.md` 與關聯文件均已同步至 GitHub `master`。
- 實際排程驗證發現每日 CSV 寫入器遺漏 `fUST`；已以測試重現並修正，commit `a6bedfa`。本機公開收集器再次執行為 `LastTaskResult=0`，fUSD／fUST／fBTC／fETH 均成功寫入新路徑。
- 已註冊並啟用 `BitfinexPublicGitHubSync`：每週一台灣時間 10:00、`pythonw.exe`、`IgnoreNew`、`StartWhenAvailable`、30 分鐘上限。手動無變更驗證為 `status=no_changes`、`LastTaskResult=0`，下次執行時間為 2026-08-31 10:00。
- 最終完整離線測試為 `276 passed, 1 deselected`。正式操作文件保留於 [`docs/PUBLIC_GITHUB_SYNC.md`](docs/PUBLIC_GITHUB_SYNC.md)；兩來源衝突判定與模型層合併仍為後續工作。

## 2026-08-24 實驗模型與 Dashboard 暫停檢查點

- `fUST` 已納入本機 funding-book 收集與原始 CSV 寫入；USD 與 USDT 仍視為不同市場，不以 `fUSD` 取代 `fUST` 的市場行為。
- 已完成目前可操作的實驗模型與本機唯讀 Dashboard，可比較本金、預設借出天數及市場預期結果；公開市場成交代理固定標示為「非常低可信度實驗值」，不可視為真實成交機率或投資建議。
- 已修正同一市場不同執行批次可能混用評估與預測的問題，並補充提前還款可能使實際利息低於完整期限估算的限制。
- 已建立 Git 安全檢查點：commit `14c5afa`（`feat: add experimental funding dashboard`），僅包含 10 個實驗模型／Dashboard 程式及測試檔；完整離線測試為 `284 passed, 1 deselected`，私人資料、`data/` 與其他未整理變更未納入提交。
- 目前介面方向已獲使用者接受，但正式 P0 尚未完成官方收益規則、歷史成交統計、資金配置、walk-forward 基準比較、正式多格式輸出及每日分析排程。
- 結案報告可先採用實驗結果，前提是明確揭露資料量及成交代理限制；正式結論仍須等待 USDT 公開資料達 60 天品質門檻後再更新。
- P1 本機公開／私人收集器維持既有排程繼續收集；GitHub 輔助收集及兩來源合併規則暫緩，不擴大本階段範圍。
- 專案開發暫停於本檢查點，先處理其他事項；尚未推送或合併目前安全檢查點分支。

## 2026-08-22 P0 新版實作計畫完成

- 使用者已確認 2026-08-19 P0 權威設計內容無誤。
- 已建立逐檔案、逐測試的 [`P0 Funding Strategy Optimizer Implementation Plan`](docs/superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md)，共十個可獨立驗收任務。
- 已重整 [`docs/P0_EXECUTION_CHECKLIST.md`](docs/P0_EXECUTION_CHECKLIST.md)，將功能完成與 60 天正式資料成熟度分開追蹤。
- 盤點發現 `data/market` 已收集 `fUST`，但 `Settings.markets` 尚未把 `fUST` 納入 funding-book `data/raw`；因此列為 Task 1，避免繼續累積缺少 USDT 委託簿的資料。
- 本階段只完成計畫與文件關聯，尚未修改模型、收集器或排程程式。
- 下一步：依使用者選擇的執行方式，從 Task 1 以 TDD 開始。

## 2026-08-19 P0 放貸策略最佳化設計確認

- 已完成逐題產品需求訪談，並由使用者確認 P0 正式設計：[`docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md`](docs/superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md)。
- P0 本金由舊版 160／10,000 USDT 改為 1,000～10,000 USDT 十個級距，起始資金以每份 1,000 USDT 拆單，最多十筆。
- 已確認比較 2／5／10／30 天、1／3／6／12／24 小時重新調價、歷史分位利率、15% 手續費、複利、資金閒置及市場容量限制。
- 回測採 walk-forward，並比較固定歷史中位利率、FRR、低利率快速成交，以及有／無原利率預測模型的結果。
- 正式結果門檻改為至少連續 60 天 USDT 公開資料、每小時完整率至少 90%、最長缺口不超過 6 小時且每種策略至少 30 次驗證機會；程式可先實作，未達門檻只輸出實驗結果。
- 最終交付定為 Markdown、CSV 與本機唯讀互動介面；每天台灣時間 10:00 更新，失敗時保留上一版結果。
- 下一步：依權威規格修訂 P0 實作計畫與執行清單，經確認後才開始程式實作。

## 2026-08-19 公開與私人 CSV 每日分檔完成

- 公開市場資料改存為 `data/market/<類別>/YYYY/MM/DD/<市場>.csv`，私人帳戶資料改存為 `data/account/<資料集>/YYYY/MM/DD.csv`；日期一律依 `collected_at` 轉成 UTC。
- SQLite、metadata、狀態檔、`data/raw` 與 Windows 排程名稱維持不變。
- 已將 2026-08-16 起的 19 個舊單檔暫存備份，依 UTC 日期分割 31,547 列至 66 個目標檔，並以來源雜湊及逐列內容完成核對。
- 公開與私人收集器均已手動驗證；私人收集結果為 `status=success`，兩個 Windows 排程均已重新啟用。
- 最終資料檢查：私人每日 CSV 31,041 列與 SQLite 31,041 筆一致，公開市場 754 列，日期錯置 0、完全重複 0、舊單檔 0。
- P0 對齊、生命週期及掛單／成交配對工具均可直接讀取每日目錄；完整離線測試為 `170 passed, 1 deselected`。
- 專用備份在 31,547 列再次驗證成功後已刪除，正式每日資料保留。

## 2026-08-19 P0 回測前置框架完成

- P0 詳細進度統一記錄於 [`docs/P0_EXECUTION_CHECKLIST.md`](docs/P0_EXECUTION_CHECKLIST.md)，作為後續唯一續作依據。
- 已完成掛單生命週期表、Offers History／Funding Trades 配對稽核，以及 B1 固定利率與 B2 固定利率加固定期間的基準框架。
- 目前產物為 `p0_offer_lifecycle.csv`、`p0_offer_trade_matches.csv` 與 `p0_fixed_baselines.csv`；基準資料明確標記為 `definition_only`，尚不是收益結果。
- 目前真實稽核資料包含 50 筆唯一掛單：26 筆可配對成交、7 筆取消未成交、17 筆成交但目前 Trades 歷史範圍未涵蓋；26 筆配對資料的幣別、利率與期間一致。
- 完整離線測試為 `163 passed, 1 deselected`。
- 本段是新版設計確認前的前置成果；後續不再以私人資料滿 7 天作為唯一啟動條件。新版程式可先實作，正式結果則依 2026-08-19 權威規格的 60 天公開資料門檻判定。

## 2026-08-16 最小本機穩定收集器完成

- 新增 `bitfinex_lending.local_stable_collector`，重用既有 public API client、SQLite storage 與 CSV exporter。
- 每市場最多重試 3 次，僅重試網路／HTTP／JSON 錯誤；解析錯誤直接記錄失敗。
- 新增單次執行 lock、SQLite／CSV 保存與 `data/local-collector.log` 摘要日誌。
- 新增操作文件：`docs/LOCAL_STABLE_COLLECTOR.md`。
- 本階段沒有修改 GitHub Actions、沒有 push、沒有私有 API、沒有排程安裝。
- 驗證結果：`125 passed, 1 deselected`。
- 已註冊並啟用 Windows 工作 `BitfinexLocalStableCollector`：每小時第 47 分鐘執行，使用目前登入使用者的 `Interactive`／`Limited` 權限，工作狀態為 `Ready`。
- 已確認排程執行檔、參數、工作目錄與 10 分鐘執行上限；尚未手動提前觸發第一次 live API 收集。

## 2026-08-16 公開 market 資料收集完成

- 本機排程現在同時收集 funding book 與公開 market 資料。
- 新增 `data/market/ticker/`、`funding_stats/`、`funding_candles/`、`prices/` 四類輸出。
- 使用同一個收集時間戳去重；market 資料失敗會記錄於本機日誌，不會抹除已成功的 funding book。
- 本階段仍不包含 `data/account/`、私有 API、GitHub 同步與模型重建。

## 2026-08-16 新增策略最佳化目標

- 新增 [strategy_optimization_goals.md](strategy_optimization_goals.md)，將下一階段拆成「策略收益比較器」與「成交機率模型」。
- 新目標會比較 160 USDT、10,000 USDT、利率、期限、成交機率、資金利用率與預期本金＋利息總和。
- 目前尚未有完整的歷史掛單／成交／取消資料，因此成交機率仍不能宣稱為真實成交機率。
- 幣價上漲／下跌預測與自動下單明確排除在本階段之外。

## 2026-08-11 模型擴充批次完成

- 完成決策樹回歸模型，沿用 168 筆門檻與 80%／20% 時序切分。
- 加入 XGBoost optional dependency 與執行時偵測；本機目前未安裝，因此輸出會明確標示 `xgboost unavailable`。
- 每個已訓練市場輸出 `data/modeling/prediction_<market>.svg` 預測／實際值對照圖。
- 新增 `data/modeling/model_report.md`，整理各市場最佳模型、MAE／RMSE／R² 與人工確認限制。
- 目前本機資料：每市場 267 筆 features、265 筆有效資料；決策樹已完成實際評估，XGBoost 尚待安裝 optional dependency 後重跑。
- 驗證結果：`113 passed, 1 deselected`。

## 2026-08-11 回測批次完成

- 新增離線 `bitfinex_lending.backtesting`，只使用 validation predictions，不連線、不下單。
- 固定模擬規則：預測利率達門檻才發出信號，實際下一期利率達門檻才視為成交；預設本金 1000、單次配置 10%、每筆資料間隔 1 小時、門檻 0。
- 輸出成交率、資金利用率、平均等待時間、最大連續未成交時間、模擬總收益與模擬年化收益。
- 目前輸出：`data/modeling/backtest_results.csv`，涵蓋三市場與四個已可用模型。
- 回測結果是研究用模擬，不代表實際成交、收益或投資建議；XGBoost optional dependency 已安裝並納入三市場評估。
- 本批完整測試為 `123 passed, 1 deselected`。

## 2026-08-11 決策輔助輸出完成

- 新增 `decision_support.csv` 與 `decision_support.md`。
- 每市場依 validation RMSE 選出目前最佳模型，輸出最新預測、10%–90% 實際觀測區間、baseline_previous 比較、成交率與平均等待時間。
- 資料不足市場會輸出 `insufficient_data` 並保留限制訊息，不臆造預測。
- 所有輸出固定標示需人工確認與不自動下單。

## 2026-08-11 回測解讀與 XGBoost 完成

- 新增 `data/modeling/backtest_report.md`，依模擬總收益排序模型並列出成交率、資金利用率與等待時間。
- XGBoost 已實際加入三市場模型評估；仍須注意模型比較與回測均為離線研究結果。

## 2026-07-29 專案續作基準與結案測試影片完成

### 重要範圍說明

- 目前完成的 `Bitfinex 系統架構與資料流` 影片是**結案測試影片／技術驗證版**，用途是驗證結案呈現可能採用的資料流程、視覺語言與影片製作流程。
- 測試影片**不是正式結案報告、正式結案簡報或正式結案影片**，也不代表結案內容已定稿。
- **實際結案報告目前尚未開始製作**。正式報告仍須另行規劃章節、整理最新資料與模型結果、補齊回測與限制說明，經確認後再開始撰寫。

### 結案測試影片成果

已在隔離分支 `feature/bitfinex-system-flow-motion` 完成 25 秒 HyperFrames 測試影片：

- 成品位置：`.worktrees/bitfinex-system-flow-motion/videos/bitfinex-system-flow/renders/bitfinex-system-flow.mp4`
- 規格：1920×1080、25 秒、H.264 MP4。
- 內容：呈現 Bitfinex funding-book、GitHub Actions、Raw CSV／SQLite、特徵工程、`80 / 168` 資料門檻及 `insufficient_data` 狀態。
- 內容限制：不虛構 MAE、RMSE、R²、收益率或成交率；清楚標示系統不自動下單。
- HyperFrames 0.7.78 完整檢查：runtime、layout、motion、contrast 均無 error；文字對比 59/59 通過。
- Proof snapshots：5.5 秒、17 秒、24 秒與 24.25 秒均已產生並人工檢視。
- 專案完整離線測試：`110 passed, 1 deselected`。
- 測試影片已提交於功能分支，commit：`7c1dbcf` (`feat: deliver Bitfinex system flow motion graphic`)；尚未合併回 `master`。

### 截至目前的整體成果

- 已完成 Bitfinex Public Books 三市場 `fUSD`、`fBTC`、`fETH` 的資料收集、錯誤處理、SQLite 與 CSV 輸出。
- 已完成每小時 GitHub Actions 自動收集、UTC 每日分檔、run ID 去重與自動 commit。
- 已完成 repository raw CSV 載入、特徵工程、168 筆有效資料門檻、80%／20% 時序切分、兩個 baseline 與線性迴歸。
- 已完成每日 `18:37 UTC` 建模 workflow，並以手動 workflow run `30369249612` 完成遠端驗收。
- 最近已驗收的資料狀態為每市場 82 筆 features、80 筆有效模型資料；三市場均正確輸出 `insufficient_data`，未產生不可信的評估或預測。
- 目前尚未完成：第一次 scheduled modeling run 的留證、達 168 筆後的實際模型評估、決策樹、XGBoost、回測、業務指標、決策輔助輸出、正式 Demo 與正式結案報告。

### 下次續作起點

1. 先同步 `origin/master`，確認 collector 與每日 modeling workflow 的最新 runs 及資料筆數。
2. 補記至少一次每日 `18:37 UTC` scheduled modeling run 的成功證據。
3. 任一市場達 168 筆有效資料後，驗證 `baseline_mean`、`baseline_previous`、`linear_regression` 的真實 MAE、RMSE、R² 與 predictions。
4. 依資料成熟度決定是否進入第二階段：決策樹、XGBoost、回測與業務指標。
5. 另行建立正式結案報告規格與大綱；在此之前，測試影片僅作為呈現方式參考，不得當作正式結案成果。
6. 決定是否將 `feature/bitfinex-system-flow-motion` 合併回 `master`；合併前保留現有 worktree 與影片成品。

## 2026-07-28 同步後待辦盤點與模型資料重建

本機 `master` 已與 `origin/master` 同步，第一階段自動建模功能已合併並推送。遠端每小時 collector 已持續產生跨日資料 commits，確認 scheduled collection 正常運作。

使用同步後的完整 repository raw CSV 重新執行 `python -m bitfinex_lending.modeling`：

- 載入 8,338 筆 funding-book rows。
- 重建 243 筆 snapshot features；`fBTC`、`fETH`、`fUSD` 各 81 筆。
- 每市場各有 79 筆完整有效模型資料，距離 168 筆門檻仍差 89 筆。
- 三市場均正確輸出 `insufficient_data`。
- `model_evaluations.csv` 與 `predictions.csv` 維持只有標頭，未產生不可信的模型結果。

目前可直接執行的第一階段本機工作均已完成。待 GitHub Actions 驗收的項目為手動執行一次每日建模 workflow，以及觀察第一次 `18:37 UTC` scheduled modeling run。盤點時 GitHub CLI 的既有 token 已失效，需重新執行 `gh auth login -h github.com` 後才能觸發並讀取遠端 run 證據。決策樹、XGBoost、回測、決策輔助輸出與 Demo 屬第二階段，需在第一批 168 筆模型結果產生後另行設計與實作。

GitHub CLI 重新登入後，已完成每日建模 workflow 的手動遠端驗收：

- Workflow：`Build Bitfinex modeling dataset`
- Run ID：`30369249612`
- Event：`workflow_dispatch`
- 結果：`success`
- 執行時間：2026-07-28 14:37:06–14:37:38 UTC，job 約 32 秒
- 離線測試：110 passed, 1 deselected
- 載入 8,440 筆 raw rows，重建 246 筆 features
- `fBTC`、`fETH`、`fUSD` 各 82 筆 features、80 筆有效模型資料，均為 `insufficient_data`
- 建模輸出 commit：`941d189` (`data: rebuild modeling dataset at 2026-07-28T14:37Z [skip ci]`)
- 該 commit 僅修改 `data/modeling` 下四個固定輸出檔；raw CSV 更新來自前一個獨立 collector commit `f012ef1`

手動驗收已完成。每日 `18:37 UTC` 的第一次 scheduled modeling run 尚未發生，維持待觀察。

## 2026-07-28 自動特徵工程與第一階段建模完成

已在隔離分支 `feature/automated-feature-modeling` 完成 repository raw CSV 到模型輸出的每日管線。資料不足不阻塞執行；系統先輸出 `insufficient_data`，待歷史資料補齊後以同一命令重跑。

- 完成嚴格 raw CSV 載入、UTC 正規化、驗證、去重與特徵重建。
- 完成每市場 168 筆有效資料門檻、80%／20% 時序切分、`baseline_mean`、`baseline_previous` 與線性迴歸。
- 完成 MAE、RMSE、R²、模型狀態、評估及逐筆預測固定格式 CSV。
- 完成 `python -m bitfinex_lending.modeling` 與每日 `18:37 UTC` GitHub Actions workflow。
- 完整離線測試：`python -m pytest -q`，110 passed, 1 deselected。
- 本機 production path：載入 206 筆 raw rows，產生 6 筆特徵；`fBTC`、`fETH`、`fUSD` 各有 2 個 snapshot、0 筆完整有效模型資料，均正確輸出 `insufficient_data`。
- `model_evaluations.csv` 與 `predictions.csv` 目前只有固定標頭，未產生或宣稱任何訓練結果。

下一步是持續由每小時 collector 累積資料。任一市場達到 168 筆完整有效資料後，每日 workflow 會自動訓練並評估該市場；其他不足市場仍維持 `insufficient_data`。

## 2026-07-21 GitHub Actions 自動收集

已完成每小時自動收集 workflow、依 UTC 日期分檔的每日市場 CSV 輸出、部分市場失敗時仍提交成功資料的行為、同一 run ID 去重，以及手動觸發入口。

本機離線驗證：`python -m pytest -q`，66 passed, 1 deselected。

GitHub 遠端驗收：

- Private repository：`wayneJ1606/Bitfinex_landing`，default branch 為 `master`，workflow 已取得 `contents: write` 權限。
- 第一次手動 run `29839099062` 成功，建立自動資料 commit `9b11a66`。
- 升級至 Node.js 24 runtime 的 `actions/checkout@v6` 與 `actions/setup-python@v6` 後，第二次手動 run `29839439761` 成功，建立資料 commit `39474a1`。
- 當日 CSV 驗證結果：`fUSD=100` 列、`fBTC=54` 列、`fETH=52` 列；每檔只有一個標頭，且皆包含 2 個不同 `run_id`。
- 尚待觀察下一次每小時第 17 分鐘的 scheduled run。

## 2026-07-14 本次交接狀態

目前程式、文件與版本控制狀態：

- Git 已初始化，主分支為 `master`，首次 commit 為 `af956c6` (`chore: initialize Bitfinex lending project`)。
- 最後完整單元測試：`55 passed, 1 deselected`。
- 資料收集、SQLite 儲存、快照 CSV、特徵工程與 `modeling_features.csv` 均已實作。

目前資料狀態：

- 成功原始快照共 103 列：`fUSD=50`、`fBTC=27`、`fETH=26`。
- 每個市場目前只有 1 個成功觀測時點。
- `modeling_features` 共 3 列，每個市場 1 列。
- 因歷史觀測不足，`previous_weighted_avg_rate`、`rate_change`、`amount_change` 與 `target_next_weighted_avg_rate` 目前皆無非空值。

本次最後執行紀錄：

- run ID `620e03e7-6fd1-4afd-911b-63a3ad6cc50b` 嘗試收集三個市場。
- 因當前執行沙箱拒絕對外網路連線，三個市場皆記錄為 `failed`；這是執行環境限制，不是 Bitfinex 資料格式或程式解析錯誤。
- 失敗執行沒有新增 snapshot，現有 103 列成功資料仍完整。
- `crawl_logs` 目前為 3 筆 success 與 3 筆 failed；`error_logs` 為 3 筆。

下次續作起點：

1. 在允許對外網路的環境重新執行 `python -m bitfinex_lending`。
2. 收集成功後執行 `python -m bitfinex_lending.features`。
3. 持續累積多個觀測時點，並確認 lag、change 與 target 非空資料量。
4. 資料量足夠後，再開始 `baseline_mean` 與 `baseline_previous` 的設計與實作。

## 2026-07-14 特徵工程管線

已完成從 SQLite 快照資料批次重建建模特徵、以單一交易更新 `modeling_features`，並原子輸出 `data/csv/modeling_features.csv`。空資料會成功產生只含標頭的 CSV，錯誤會由命令邊界以非零狀態回報。

驗證證據：

- `python -m pytest tests/test_features.py -v`：7 passed
- `python -m pytest -v`：55 passed, 1 deselected
- `python -m bitfinex_lending.features`：載入 103 筆原始列，產生 3 筆特徵
- 生產 SQLite 特徵數：`fBTC=1`、`fETH=1`、`fUSD=1`；CSV 標頭與規格一致

下一個里程碑：在累積足夠歷史快照後，建立與評估基準模型。

## 專案狀態

目前狀態：新版企劃書與 PRD、資料收集 MVP、建模資料集與特徵工程管線均已完成。現階段先累積多個觀測時點的歷史快照，再進入基準模型。

專案已從原本的「放貸資料收集系統」調整為「放貸市場決策輔助系統」。新方向保留資料收集與建模學習重點，但加入現實可用所需的回測、業務指標、風險提示與人工確認流程。

## 已完成事項

- 閱讀原始 Bitfinex 放貸資料收集企劃書。
- 釐清原始需求：本機排程抓取 `fUSD`、`fBTC`、`fETH`，保存 SQLite / CSV。
- 建立第一版 `prd.md`、`progress.md`、`todo.md`。
- 依新的學習重點，建立「Bitfinex 放貸利率預測與模型評估」企劃書。
- 釐清模型不能直接套用到真實放貸決策，需加入成交機率、資金利用率、回測與風險控管。
- 建立新版企劃書：`專案企劃書_Bitfinex放貸決策輔助系統_現實可用版.md`。
- 產出新版 Word 檔：`專案企劃書_Bitfinex放貸決策輔助系統_現實可用版.docx`。
- 更新 `prd.md` 為「Bitfinex 放貸市場決策輔助系統 PRD」。
- 完成 `todo.md` 中「需求與設計」項目，並建立 `requirements_design.md`。

## 目前產品決策

### 使用目的

本專案主要供專案作者本人觀察 Bitfinex 放貸市場，並練習將業務問題轉化為結構型資料建模與回測任務。

### 產品定位

系統定位為「決策輔助原型」，不是自動交易或自動放貸系統。

系統可以提供：

- 建議觀察利率區間
- 模型預測值與信心提示
- 模擬成交率
- 資金利用率
- 平均等待時間
- 回測與模型評估報告
- 風險提示與人工確認提醒

系統不做：

- 自動下單
- 自動放貸
- 保證收益
- 直接投資建議
- 使用私人 API key 操作帳戶

### 核心資料範圍

本次必抓 Bitfinex funding markets：

- `fUSD`
- `fBTC`
- `fETH`

資料來源以 Bitfinex Public Books endpoint 為主。

### 核心建模範圍

本次模型與策略包含：

- baseline：平均值預測或前一期利率預測
- 線性迴歸
- 決策樹
- XGBoost

模型評估指標包含：

- MAE
- RMSE
- R2

### 核心回測範圍

回測需比較：

- baseline 策略
- 模型策略

業務指標包含：

- 模擬成交率
- 資金利用率
- 平均等待時間
- 最大連續未成交時間
- 模擬年化收益
- 與 baseline 策略的差異

## 下一步

下一個里程碑：

1. 持續收集資料，讓每個市場累積多個觀測時點。
2. 確認 lag、change 與 next target 欄位有足夠非空資料。
3. 建立 `baseline_mean` 與 `baseline_previous`，並使用時間序列切分進行評估。

## 2026-07-14 資料收集 MVP

已完成：

- 建立 Python 3.11+ 套件與 `python -m bitfinex_lending` 單次執行入口。
- 實作 Bitfinex Public Books client、嚴格欄位解析與穩定錯誤分類。
- 實作 `fUSD`、`fBTC`、`fETH` 依序抓取；個別市場失敗時繼續執行。
- 建立 SQLite `funding_book_snapshots`、`crawl_logs`、`error_logs` 與 transaction 寫入。
- 建立原子化 UTF-8 快照 CSV 輸出。
- 建立操作說明、Windows 工作排程器設定與 opt-in live smoke test。

驗證結果：

- `python -m pytest -v`：26 passed、1 integration test deselected。
- `python -m pytest -m integration tests/integration/test_live_api.py -v`：1 passed。
- 真實三市場執行 run ID：`36ee2a23-692d-444f-9bb4-7dc3ab24a288`。
- 寫入筆數：`fUSD=50`、`fBTC=27`、`fETH=26`，三市場皆成功，error log 為 0。
- 產出 SQLite：`data/bitfinex_lending.sqlite3`，以及三份快照 CSV。

## 風險與注意事項

- funding book 是即時市場資料，若收集時間不足，模型與回測結果可能不穩定。
- 模型分數好不代表真實放貸結果好，需用成交率、等待時間與資金利用率一起評估。
- XGBoost 不一定優於簡單模型，需與 baseline 比較。
- 成交機率估計需要明確定義模擬規則，否則容易產生誤導。
- 系統必須明確標示不自動下單、需人工確認。
- API 格式若變更，資料解析邏輯需調整。
## 私有 Funding 唯讀收集器

- [x] 唯讀 authenticated client 與權限檢查
- [x] Funding 資料本機儲存與去重
- [x] 私有 Funding collector 串接
- [x] 本機憑證讀取與 `--dry-run`
- [x] 排程安裝腳本（預覽模式；尚未啟用）
