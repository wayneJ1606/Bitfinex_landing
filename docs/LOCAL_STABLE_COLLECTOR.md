# 最小本機穩定收集器

## 本階段範圍

- 收集公開 funding book：`fUSD`、`fUST`、`fBTC`、`fETH`
- 收集公開 ticker、funding statistics、funding candles 與 `tBTCUSD`／`tETHUSD` 價格
- 使用既有 Bitfinex public API client、SQLite storage 與每日 CSV exporter
- 每個市場失敗時最多重試 3 次，等待時間採遞增延遲
- 同一時間只允許一個本機收集程序執行
- 保存 SQLite、每日 CSV 與一行式執行摘要日誌

本收集器本身不直接 push GitHub，也不包含私有 API、帳戶事件、模型、回測或自動下單。公開資料另由每週白名單同步工作上傳。

## 執行

```powershell
python -m bitfinex_lending.local_stable_collector
```

## Windows 每小時排程

先預覽排程設定，不會註冊工作：

```powershell
.\scripts\install-minimal-local-collector.ps1
```

確認輸出中的 Python 路徑、專案目錄與 `minute=47` 後，再明確啟用：

```powershell
.\scripts\install-minimal-local-collector.ps1 -Enable -Confirm
```

若已確認預覽內容，也可直接使用：

```powershell
.\scripts\install-minimal-local-collector.ps1 -Enable
```

排程只會執行本機公開資料收集器；不推送 GitHub、不連接私有 API、不執行模型或下單。工作使用目前登入使用者的 `Interactive`／`Limited` 權限，每小時執行一次，同時執行時採 `IgnoreNew`，單次最多 10 分鐘。

可調整重試參數：

```powershell
python -m bitfinex_lending.local_stable_collector `
  --max-attempts 3 `
  --retry-delay 2 `
  --lock-path data/local-collector.lock `
  --log-path data/local-collector.log
```

本機公開資料與 GitHub Actions 資料分開保存：

- SQLite：`data/bitfinex_lending.sqlite3`
- CSV：`data/local_public/raw/YYYY/MM/DD/<market>.csv`
- 日誌：`data/local-collector.log`
- 公開 market 資料：`data/local_public/market/ticker/`、`data/local_public/market/funding_stats/`、`data/local_public/market/funding_candles/`、`data/local_public/market/prices/`

## 可靠性界線

- 只對網路錯誤、HTTP 錯誤與 JSON 解碼錯誤重試。
- 解析錯誤不重試，避免把格式問題隱藏起來。
- lock 檔存在時直接跳過，不同時啟動第二個收集程序。
- 本機成功資料不會在每小時收集完成後立即推送 GitHub；每週同步失敗也不影響收集。
- GitHub 與本機公開資料目前分開保存，兩來源衝突判定與模型層合併仍是後續工作。
