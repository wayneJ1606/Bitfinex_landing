# Bitfinex 放貸市場決策輔助系統需求與設計

## 1. 整體資料流程

系統資料流程分為 8 個階段：

1. 資料抓取：呼叫 Bitfinex Public Books endpoint，抓取 `fUSD`、`fBTC`、`fETH` funding book。
2. 原始整理：將 API 回傳資料整理成固定欄位，包含 market、rate、period、count、amount、side、fetched_at。
3. 資料保存：將整理後的 funding book 快照寫入 SQLite，並可輸出 CSV。
4. 特徵工程：依每次快照彙總出建模特徵，例如 weighted_avg_rate、total_amount、rate_spread、previous_weighted_avg_rate。
5. 建模資料集產生：將特徵與下一期目標欄位合併成 supervised learning dataset。
6. 模型訓練與評估：訓練 baseline、線性迴歸、決策樹、XGBoost，輸出 MAE、RMSE、R2。
7. 回測：用歷史資料比較 baseline 策略與模型策略，計算成交率、資金利用率、等待時間與模擬收益。
8. 決策輔助輸出：產生建議觀察利率區間、模型預測、策略比較、風險提示與人工確認提醒。

## 2. SQLite Schema 設計

### 2.1 `funding_book_snapshots`

保存每次 API 抓取後整理出的 funding book 明細。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| market | TEXT | 市場代號，例如 `fUSD` |
| rate | REAL | 利率 |
| period | INTEGER | 放貸期間 |
| count | INTEGER | 彙總筆數 |
| amount | REAL | 數量 |
| side | TEXT | `offer` 或 `demand`，依 amount 正負值判斷 |
| fetched_at | TEXT | 抓取時間，ISO 8601 格式 |
| source_url | TEXT | API 來源 |
| raw_data | TEXT | 原始資料 JSON 字串 |

### 2.2 `crawl_logs`

保存每次爬取執行紀錄。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| started_at | TEXT | 開始時間 |
| ended_at | TEXT | 結束時間 |
| status | TEXT | `success`、`partial_success`、`failed` |
| markets | TEXT | 本次抓取 markets |
| rows_saved | INTEGER | 寫入筆數 |
| message | TEXT | 補充訊息 |

### 2.3 `error_logs`

保存 API、資料解析、儲存與模型流程錯誤。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| occurred_at | TEXT | 發生時間 |
| stage | TEXT | `api`、`parse`、`storage`、`feature`、`model`、`backtest` |
| market | TEXT | 相關 market，可為空 |
| error_type | TEXT | 錯誤類型 |
| message | TEXT | 錯誤訊息 |
| raw_context | TEXT | 相關上下文 |

### 2.4 `modeling_features`

保存每個 market、每個觀察時間點的建模資料。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| market | TEXT | 市場代號 |
| feature_time | TEXT | 特徵對應時間 |
| hour | INTEGER | 小時 |
| day_of_week | INTEGER | 星期，0-6 |
| avg_rate | REAL | 平均利率 |
| weighted_avg_rate | REAL | 依 amount 加權平均利率 |
| min_rate | REAL | 最低利率 |
| max_rate | REAL | 最高利率 |
| total_amount | REAL | 總數量 |
| avg_period | REAL | 平均期間 |
| offer_count | INTEGER | offer 筆數 |
| demand_count | INTEGER | demand 筆數 |
| rate_spread | REAL | max_rate - min_rate |
| previous_weighted_avg_rate | REAL | 前一期加權平均利率 |
| rate_change | REAL | 本期與前一期利率差 |
| amount_change | REAL | 本期與前一期總數量差 |
| target_next_weighted_avg_rate | REAL | 下一期加權平均利率 |

### 2.5 `model_evaluations`

保存每次模型訓練與驗證結果。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| run_at | TEXT | 評估時間 |
| market | TEXT | 市場代號或 `all` |
| model_name | TEXT | `baseline_mean`、`baseline_previous`、`linear_regression`、`decision_tree`、`xgboost` |
| train_start | TEXT | 訓練資料起始時間 |
| train_end | TEXT | 訓練資料結束時間 |
| valid_start | TEXT | 驗證資料起始時間 |
| valid_end | TEXT | 驗證資料結束時間 |
| mae | REAL | MAE |
| rmse | REAL | RMSE |
| r2 | REAL | R2 |
| notes | TEXT | 模型限制或補充 |

### 2.6 `backtest_results`

保存 baseline 策略與模型策略的回測結果。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| run_at | TEXT | 回測時間 |
| market | TEXT | 市場代號 |
| strategy_name | TEXT | 策略名稱 |
| start_time | TEXT | 回測起始時間 |
| end_time | TEXT | 回測結束時間 |
| simulated_orders | INTEGER | 模擬掛單次數 |
| simulated_fills | INTEGER | 模擬成交次數 |
| fill_rate | REAL | 模擬成交率 |
| utilization_rate | REAL | 資金利用率 |
| avg_wait_minutes | REAL | 平均等待時間 |
| max_unfilled_streak | INTEGER | 最大連續未成交次數 |
| simulated_annualized_return | REAL | 模擬年化收益 |
| notes | TEXT | 回測假設與限制 |

### 2.7 `decision_outputs`

保存決策輔助輸出紀錄。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| id | INTEGER PRIMARY KEY | 流水號 |
| generated_at | TEXT | 產生時間 |
| market | TEXT | 市場代號 |
| recommended_rate_low | REAL | 建議觀察利率下限 |
| recommended_rate_high | REAL | 建議觀察利率上限 |
| predicted_rate | REAL | 模型預測利率 |
| confidence_label | TEXT | `low`、`medium`、`high` |
| baseline_comparison | TEXT | 與 baseline 比較摘要 |
| risk_notes | TEXT | 風險提示 |
| requires_manual_confirmation | INTEGER | 固定為 1 |

## 3. CSV 輸出格式

第一版需支援 4 類 CSV：

| 檔案 | 來源 | 用途 |
| --- | --- | --- |
| `funding_book_snapshots.csv` | `funding_book_snapshots` | 檢視原始整理資料 |
| `modeling_features.csv` | `modeling_features` | 模型訓練輸入 |
| `model_evaluations.csv` | `model_evaluations` | 模型比較與報告 |
| `backtest_results.csv` | `backtest_results` | 回測與業務指標報告 |

CSV 欄位名稱需與 SQLite 欄位一致，時間欄位使用 ISO 8601 字串，方便用 Pandas、Excel 或簡報工具讀取。

## 4. 建模資料集格式

一列資料代表某個 market 在某個觀察時間點的 funding book 彙總狀態。

第一版建模資料集欄位：

- `market`
- `feature_time`
- `hour`
- `day_of_week`
- `avg_rate`
- `weighted_avg_rate`
- `min_rate`
- `max_rate`
- `total_amount`
- `avg_period`
- `offer_count`
- `demand_count`
- `rate_spread`
- `previous_weighted_avg_rate`
- `rate_change`
- `amount_change`
- `target_next_weighted_avg_rate`

資料切分原則：

- 以時間順序切分，不隨機打散。
- 前 80% 作為訓練資料，後 20% 作為驗證資料。
- 同一 market 的時間順序不可被破壞。

## 5. Baseline 策略定義

第一版包含兩個 baseline：

### 5.1 `baseline_mean`

使用訓練資料的平均 `target_next_weighted_avg_rate` 作為所有驗證資料的預測值。

用途：

- 檢查模型是否至少優於「永遠猜平均值」。

### 5.2 `baseline_previous`

使用 `previous_weighted_avg_rate` 或當期 `weighted_avg_rate` 作為下一期預測值。

用途：

- 檢查模型是否優於「假設下一期等於目前市場狀態」。

## 6. 模型策略輸出格式

每個模型需輸出同一格式，方便比較與回測。

欄位：

- `market`
- `feature_time`
- `model_name`
- `predicted_rate`
- `actual_next_rate`
- `prediction_error`
- `recommended_rate_low`
- `recommended_rate_high`
- `confidence_label`

建議利率區間第一版規則：

- `recommended_rate_low = predicted_rate - validation_mae`
- `recommended_rate_high = predicted_rate + validation_mae`

信心標籤第一版規則：

- `high`：模型 MAE 優於兩個 baseline，且驗證資料量足夠。
- `medium`：模型 MAE 優於其中一個 baseline。
- `low`：模型未優於 baseline，或資料量不足。

## 7. 回測規則

第一版回測以「模擬觀察」為主，不模擬真實下單。

### 7.1 Baseline 策略

baseline 策略使用 `baseline_previous` 的預測值作為觀察利率。

模擬規則：

- 每個觀察時間點產生一個觀察利率。
- 若後續 N 個觀察點內，市場 `weighted_avg_rate` 達到或高於觀察利率，視為模擬成交。
- N 第一版設定為 3，可在後續實作中改為設定檔。

### 7.2 模型策略

模型策略使用模型輸出的 `recommended_rate_low` 到 `recommended_rate_high` 作為觀察區間。

模擬規則：

- 若後續 N 個觀察點內，市場 `weighted_avg_rate` 落在建議區間內或高於區間下限，視為模擬成交。
- 若模型信心為 `low`，該筆只記錄觀察，不納入操作型回測。

### 7.3 業務指標

- 模擬成交率：`simulated_fills / simulated_orders`
- 資金利用率：模擬成交期間占全部觀察期間的比例
- 平均等待時間：成交所需觀察點數換算成分鐘
- 最大連續未成交時間：連續未成交觀察點數
- 模擬年化收益：以成交時觀察利率估算，需在報告中標示為模擬值

## 8. 決策輔助輸出格式

每次產生決策輔助結果時，輸出以下內容：

- market
- generated_at
- recommended_rate_low
- recommended_rate_high
- predicted_rate
- confidence_label
- baseline_comparison
- recent_market_summary
- backtest_summary
- risk_notes
- requires_manual_confirmation

輸出原則：

- `requires_manual_confirmation` 固定為 true。
- 若資料量不足，僅輸出市場觀察，不輸出操作型建議。
- 若模型未優於 baseline，需明確提示「模型未優於 baseline」。
- 所有文字輸出需包含「不自動下單、不保證收益、需人工確認」。

## 9. 第一版設計邊界

第一版只處理公開資料與本機分析流程。

本階段不做：

- 使用 Bitfinex authenticated API
- 自動下單
- 自動放貸
- 真實資金操作
- 保證收益估算
- 雲端部署
- 即時通知
