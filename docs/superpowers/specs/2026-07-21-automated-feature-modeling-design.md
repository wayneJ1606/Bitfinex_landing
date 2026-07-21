# GitHub 自動特徵工程與第一階段建模設計

## 目標

以 repository 中持續累積的 `data/raw/**/*.csv` 作為雲端分析來源，每日由 GitHub Actions 重建完整建模特徵。當單一市場累積至少 168 個具有預測目標的有效觀測時點後，自動訓練並評估 `baseline_mean`、`baseline_previous` 與線性迴歸，將可閱讀的特徵、狀態、評估與預測 CSV 提交回 repository。

本階段建立可信、可重現的資料與評估管線，不執行真實下單、不使用私人 API，也不輸出操作型投資建議。

## 範圍

包含：

- 從多日、每日分市場 CSV 載入原始 funding-book rows。
- 嚴格驗證、去重、排序與彙總。
- 重建目前已定義的 lag、change 與 next-period target 特徵。
- 每個市場獨立檢查 168 個有效時點的建模門檻。
- 80%／20% 時序切分。
- `baseline_mean`、`baseline_previous` 與線性迴歸的預測和評估。
- MAE、RMSE 與 R² 輸出。
- 每日與手動 GitHub Actions workflow。

不包含：

- 決策樹、XGBoost、超參數搜尋與交叉驗證。
- 回測、成交率、資金利用率與年化收益。
- 建議放貸利率區間或信心標籤。
- 二進位模型檔保存。
- SQLite 作為 GitHub runner 間的持久資料來源。

## 資料來源與來源優先權

雲端批次管線的正式來源為：

```text
data/raw/YYYY/MM/DD/fUSD.csv
data/raw/YYYY/MM/DD/fBTC.csv
data/raw/YYYY/MM/DD/fETH.csv
```

每個檔案必須使用欄位：

```text
run_id,market,rate,period,count,amount,side,fetched_at
```

GitHub runner 中的 SQLite 每次執行後會消失，因此不參與雲端特徵重建。既有 SQLite 特徵流程保留供本機探索，但新自動管線以 raw CSV 為唯一輸入，避免同一次執行混用兩個來源。

## 原始 CSV 載入與驗證

載入器遞迴尋找 `data/raw/**/*.csv`，以正規化的 repository-relative path 排序後逐檔讀取。

每個檔案必須符合：

- UTF-8 編碼。
- 標頭與規格完全一致，不允許缺少、重複或額外欄位。
- 路徑檔名市場與每一列 `market` 相同。
- `market` 只能是 `fUSD`、`fBTC`、`fETH`。
- `run_id` 與 `fetched_at` 不得為空。
- `fetched_at` 是含時區的 ISO 8601，排序前轉為 UTC。
- `rate`、`amount` 是有限浮點數。
- `period` 是正整數，`count` 是非負整數。
- `amount` 不得為零；`offer` 對應正 amount，`demand` 對應負 amount。

去重鍵為完整正規化 row：

```text
(run_id, market, normalized_fetched_at, rate, period, count, amount, side)
```

完全相同的重複 row 只保留一列。若同一 `(run_id, market)` 出現不同 `fetched_at`，或同一路徑市場與 row market 不一致，視為資料損壞並使整次管線失敗。

任一輸入檔無法解析時不忽略該檔，也不產生新的輸出。

## 特徵語意

一筆特徵代表一個 `(market, fetched_at)` snapshot。沿用既有特徵定義：

- `market`
- `feature_time`：正規化為 UTC ISO 8601。
- `hour`、`day_of_week`：UTC 時間欄位。
- `avg_rate`
- `weighted_avg_rate`：以 `abs(amount)` 加權。
- `min_rate`、`max_rate`
- `total_amount`：`sum(abs(amount))`。
- `avg_period`
- `offer_count`、`demand_count`：依 side 加總 source `count`。
- `rate_spread`
- `previous_weighted_avg_rate`
- `rate_change`
- `amount_change`
- `target_next_weighted_avg_rate`

同一市場獨立依 UTC 時間排序。第一筆的 lag／change 為空，最後一筆的 target 為空。所有 snapshot 都保留在特徵輸出；模型資料只使用 target 非空的 rows。

## 輸出檔案

管線產生：

```text
data/modeling/modeling_features.csv
data/modeling/model_status.csv
data/modeling/model_evaluations.csv
data/modeling/predictions.csv
```

### `modeling_features.csv`

使用上述固定特徵欄位，依 `market, feature_time` 排序。空 lag 或 target 寫成空欄位。

### `model_status.csv`

固定欄位：

```text
market,status,feature_rows,valid_rows,required_rows,message
```

狀態值：

- `insufficient_data`：`valid_rows < 168`。
- `trained`：該市場三個模型均完成評估。
- `failed` 不寫入成功輸出；模型或資料錯誤使整個命令非零結束，保留 repository 上一次成功 commit。

門檻以 target 非空的 `valid_rows` 計算，不以包含最後一筆空 target 的 `feature_rows` 計算。

### `model_evaluations.csv`

固定欄位：

```text
run_at,market,model_name,train_rows,valid_rows,train_start,train_end,valid_start,valid_end,mae,rmse,r2
```

僅包含狀態為 `trained` 的市場，每市場固定三列：`baseline_mean`、`baseline_previous`、`linear_regression`。

### `predictions.csv`

固定欄位：

```text
run_at,market,feature_time,model_name,predicted_rate,actual_next_rate,prediction_error
```

每個已訓練市場、每個驗證 row、每個模型一列。`prediction_error = predicted_rate - actual_next_rate`。

所有輸出使用 UTF-8、固定欄位與確定性排序。先在 runner 暫存位置完整建立全部檔案；只有命令成功時 workflow 才 stage 和 commit `data/modeling`。命令失敗時 GitHub runner 被丟棄，遠端 repository 保留上一次成功輸出。

## 時序切分與模型

每個市場獨立處理，模型輸入 rows 依 `feature_time` 由舊到新排序，禁止 shuffle。

對 `n` 筆有效 rows：

```text
train_size = floor(n * 0.8)
validation = rows[train_size:]
```

168 筆門檻下至少有 134 筆訓練 rows 與 34 筆驗證 rows。若計算結果無法同時提供非空訓練集與驗證集，視為內部驗證錯誤。

### `baseline_mean`

只使用訓練集 target 平均值，對全部驗證 rows 預測同一值，不得讀取驗證 target 計算平均。

### `baseline_previous`

使用每筆驗證 row 的當期 `weighted_avg_rate` 預測下一期 target。

### `linear_regression`

使用 `scikit-learn` 的 `LinearRegression`。第一階段輸入欄位固定為：

```text
hour,day_of_week,avg_rate,weighted_avg_rate,min_rate,max_rate,total_amount,
avg_period,offer_count,demand_count,rate_spread,previous_weighted_avg_rate,
rate_change,amount_change
```

因第一筆特徵的 lag 欄位為空，模型輸入前排除任何 predictor 或 target 為空的 row。168 門檻在此清理後計算，因此 `valid_rows` 是真正可供三個模型共同比較的 row 數。

不進行隨機標準化、缺值填補或特徵選擇，確保第一版行為可解釋且可重現。

## 評估指標

每個模型在相同驗證 rows 上計算：

- MAE
- RMSE
- R²

使用 `scikit-learn` 指標函式。驗證集必須完全相同，確保模型比較公平。R² 若因驗證資料退化而不是有限數字，整個模型執行失敗，不提交誤導性結果。

## 命令介面

新增獨立命令：

```powershell
python -m bitfinex_lending.modeling
```

預設輸入 `data/raw`，輸出 `data/modeling`，成功時列印每個市場的 feature rows、valid rows 與狀態，再列印輸出路徑。全部市場資料不足仍是成功狀態，因為特徵與不足狀態是有效輸出。

命令 exit code：

- `0`：所有 raw CSV 均有效，特徵與狀態輸出成功；達門檻的市場也完成模型評估。
- `1`：輸入、特徵、模型、指標或輸出失敗。

正常錯誤以 `fatal: <message>` 輸出至 stderr，不顯示 stack trace 或 secret。

## GitHub Actions

新增每日 workflow：

```text
.github/workflows/build-modeling-dataset.yml
```

觸發方式：

- 每日 `18:37 UTC`，即台灣時間翌日 `02:37`。
- `workflow_dispatch` 手動執行。

工作步驟：

1. Checkout `master` 最新狀態，使用完整 Git history。
2. 設定 Python 3.11 與 pip cache。
3. 安裝專案與 modeling dependencies。
4. 執行完整離線測試。
5. 執行 `python -m bitfinex_lending.modeling`。
6. 只 stage `data/modeling`。
7. 無變更時不 commit；有變更時以 `[skip ci]` commit 並 push。
8. push 被遠端每小時 collector 更新拒絕時，執行一次 `git pull --rebase` 後重試，不 force push。

每日 workflow 與每小時 collector 使用同一個 concurrency group，`cancel-in-progress: false`，避免兩個 write-capable workflows 同時修改 `master`。排程可能延遲，模型 `run_at` 使用實際 UTC 執行時間。

Workflow 只使用內建 `GITHUB_TOKEN` 與 `contents: write`，不需要新增 secret。

## 套件與版本

在 modeling optional dependency group 加入相容 Python 3.11+ 的 `scikit-learn` 版本範圍。一般 collector 安裝維持只需要 `requests`；每日 modeling workflow 安裝 `.[test,modeling]`，避免每小時 collector 承擔不必要的科學運算套件安裝成本。

## 錯誤與資料保護

- 任一 raw CSV 損壞：整次命令失敗。
- 單一市場資料不足：輸出 `insufficient_data`，其他市場仍可訓練。
- 單一已達門檻市場訓練或指標失敗：整次命令失敗，不 commit 部分新輸出。
- 輸出前所有資料與模型結果先在記憶體中完成。
- 每個 CSV 使用暫存檔與原子替換。
- GitHub 只在命令、測試與全部輸出成功後 commit。
- 遠端 push 衝突未能在一次 rebase 後解決：workflow 失敗，保留遠端上次成功輸出，下一次可重跑。

## 測試與驗收

開發遵循 TDD，至少覆蓋：

- 多目錄、多市場載入順序與正確型別轉換。
- 缺少、額外、重複欄位和非 UTF-8 輸入。
- 路徑市場不符、未知市場、時區錯誤與無效數值。
- 完整 row 去重及衝突 snapshot metadata。
- UTC 跨日排序、lag、change 與 next target。
- 167／168 有效 rows 的門檻邊界。
- 80%／20% 時序切分且無 shuffle、無未來資料洩漏。
- 兩個 baseline 的預測公式。
- 線性迴歸固定 predictor schema。
- 三模型使用相同驗證 rows。
- MAE、RMSE、R² 與 predictions 誤差。
- 一個市場不足但其他市場正常訓練。
- 全部市場不足仍成功輸出狀態與空評估／預測 CSV。
- 輸出標頭、排序、原子替換與失敗清理。
- CLI 成功摘要及錯誤 exit code。
- GitHub workflow cron、手動入口、權限、共用 concurrency、測試先於建模、stage 範圍與失敗傳遞。

本機驗收：

1. 完整離線測試通過。
2. 對目前 repository raw CSV 執行命令。
3. 確認三個市場皆產生特徵，狀態為 `insufficient_data`。
4. 確認 `model_evaluations.csv` 與 `predictions.csv` 只有標頭。

GitHub 驗收：

1. 手動執行每日 modeling workflow。
2. 確認產生 `data/modeling` 自動 commit。
3. 確認 raw CSV 不被 workflow 改寫。
4. 觀察至少一次每日 scheduled run。

## 後續階段

當一週資料達到門檻並產生第一批可信評估後，再依 baseline 結果設計第二階段：決策樹、XGBoost、walk-forward validation、回測與決策輔助輸出。第一階段不預先加入這些複雜度。
