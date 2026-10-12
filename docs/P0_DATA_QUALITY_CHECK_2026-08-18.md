# P0 資料品質初步檢查

檢查日期：2026-08-18

## 目前結果

資料來源：`data/account/account_events.sqlite3`、`data/metadata/account_collector_status.json`

- 收集時間點：480
- 收集範圍：2026-08-16 14:16 UTC 至 2026-08-18 06:15 UTC，約 40 小時
- Funding Offers：956 筆事件，2 個不同事件 ID
- Funding Trades：12,000 筆事件，25 個不同事件 ID
- Funding Loans：480 筆事件，1 個不同事件 ID
- Funding Credits：3 筆事件，1 個不同事件 ID；之後回傳空結果
- 重複事件鍵：0
- 最新 Metadata 狀態：`success`
- 最新端點失敗：0

## 判讀

目前排程與儲存正常，收集時間點接近每 5 分鐘一次，沒有發現重複事件或端點錯誤。Funding Credits 後續沒有新增，與目前沒有進行中 Credit 的情況一致，不代表收集器停止。

## P0 決策

目前資料品質可以繼續累積，但樣本只有約兩天，尚不足以開始正式回測或宣稱最佳利率。先維持排程至至少 7 天；下一次檢查再計算每小時覆蓋率、時間缺口與成交事件分布，之後才建立固定利率基準與期望收益比較。
