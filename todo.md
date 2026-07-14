# Bitfinex 放貸市場決策輔助系統待辦清單

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
- [ ] 實作模型評估表輸出 CSV
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

- [ ] 建立訓練集與驗證集切分流程
- [ ] 建立 baseline：平均值預測
- [ ] 建立 baseline：前一期利率預測
- [ ] 訓練線性迴歸模型
- [ ] 訓練決策樹模型
- [ ] 訓練 XGBoost 模型
- [ ] 輸出 MAE
- [ ] 輸出 RMSE
- [ ] 輸出 R2
- [ ] 建立模型比較表
- [ ] 建立預測值與實際值比較圖
- [ ] 撰寫模型結果解讀

## 回測與業務指標

- [ ] 定義 baseline 策略的回測規則
- [ ] 定義模型策略的回測規則
- [ ] 實作 baseline 策略回測
- [ ] 實作模型策略回測
- [ ] 計算模擬成交率
- [ ] 計算資金利用率
- [ ] 計算平均等待時間
- [ ] 計算最大連續未成交時間
- [ ] 計算模擬年化收益
- [ ] 比較模型策略與 baseline 策略差異
- [ ] 撰寫回測結果解讀

## 決策輔助輸出

- [ ] 輸出建議觀察利率區間
- [ ] 輸出模型預測值
- [ ] 輸出模型信心或限制提示
- [ ] 輸出 baseline 策略比較
- [ ] 輸出模擬成交率與等待時間
- [ ] 輸出風險與使用限制
- [ ] 明確標示需人工確認
- [ ] 確認系統不執行任何真實下單或帳戶操作

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
- [ ] 可建立 baseline
- [ ] 可訓練線性迴歸
- [ ] 可訓練決策樹
- [ ] 可訓練 XGBoost
- [ ] 可輸出 MAE、RMSE、R2
- [ ] 可比較各模型表現
- [ ] 可執行 baseline 策略回測
- [ ] 可執行模型策略回測
- [ ] 可計算模擬成交率
- [ ] 可計算資金利用率
- [ ] 可計算平均等待時間
- [ ] 可輸出建議觀察利率區間
- [ ] 可顯示風險與使用限制
- [ ] 所有建議明確標示需人工確認
- [ ] 系統不自動下單
- [ ] 文件足以讓使用者安裝、執行、訓練模型、執行回測與查看結果
