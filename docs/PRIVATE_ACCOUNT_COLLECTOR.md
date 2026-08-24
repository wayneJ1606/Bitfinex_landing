# 私有 Funding 唯讀資料收集器

此收集器只讀取本人 Bitfinex Funding 資料，不會下單、撤單、轉帳或提領。

## API Key 權限

請在 Bitfinex 建立獨立 API Key，只開啟：

- `funding: READ`
- `history: READ`

所有 WRITE 權限、Orders、Withdraw、Transfer 與 Settings Write 都必須關閉。API Secret 不要貼到對話、寫入程式碼或提交 Git。

## 本機憑證

在執行程序的 Windows 使用者環境中設定：

```powershell
$env:BITFINEX_READONLY_API_KEY = "你的唯讀 API Key"
$env:BITFINEX_READONLY_API_SECRET = "你的唯讀 API Secret"
```

正式排程不應把 Secret 直接寫入 PowerShell 腳本；建議使用 Windows Credential Manager 或受保護的使用者環境變數。

## 先做 Dry Run

只檢查權限，不收集資料：

```powershell
python -m bitfinex_lending.private_account_collector --dry-run
```

成功時會顯示已確認唯讀權限。若缺少憑證、權限含 WRITE 或權限不足，程序會停止。

## 手動收集

```powershell
python -m bitfinex_lending.private_account_collector
```

資料依 UTC 日期寫入本機，並由 `.gitignore` 永久排除：

```text
data/account/
  funding_offers/YYYY/MM/DD.csv
  funding_trades/YYYY/MM/DD.csv
  funding_loans/YYYY/MM/DD.csv
  funding_credits/YYYY/MM/DD.csv
  account_events.sqlite3

data/metadata/account_collector_status.json
```

私人資料只留在本機。GitHub 只同步本收集器的程式、測試、排程腳本與說明文件。

## 目前驗證狀態

- 單元測試與完整測試均通過。
- 缺少憑證時會以錯誤碼 2 停止，且不發送 authenticated request。
- 排程腳本預覽不會呼叫 Windows Task Scheduler API。
- `BitfinexPrivateAccountCollector` 已由使用者完成註冊、啟用與手動觸發驗證。
- 實際收集狀態已確認為 `success`，排程持續累積本機私人資料。
