# Bitfinex 放貸市場決策輔助系統進度紀錄

## 2026-07-21 自動特徵工程與建模續作盤點

目前開發已從 `master` 的設計／實作計畫，進入隔離分支
`feature/automated-feature-modeling`。兩次中斷的成果均已提交，工作樹乾淨，沒有遺失或未提交修改。

- Task 1「Repository 原始 CSV 載入器」已完成：包含遞迴掃描、嚴格欄位與路徑驗證、UTC 正規化、精確列去重及衝突檢查。
- Task 1 實作位於 `bitfinex_lending/raw_csv.py`，測試位於 `tests/test_raw_csv.py`。
- 功能分支基準驗證：`python -m pytest -q` 為 `94 passed, 1 deselected`。
- Task 2–5 尚待完成：模型訓練、固定格式輸出／CLI、每日建模 workflow、文件與正式驗收。
- Repository 目前只有每個市場 2 個 snapshot；模型需每個市場至少 168 筆有效特徵觀測，因此現階段預期輸出 `insufficient_data`，不會訓練模型。

下一個實作點是 Task 2：`baseline_mean`、`baseline_previous`、`linear_regression`、時序 80/20 切分與 MAE／RMSE／R²。

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
