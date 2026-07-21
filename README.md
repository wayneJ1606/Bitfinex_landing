# Bitfinex 放貸市場資料收集器

這是一個單次執行的 Bitfinex Public Books 資料收集程式。每次執行會依序抓取 `fUSD`、`fBTC`、`fETH`，把 funding book 快照與執行紀錄寫入 SQLite，並為成功且非空的市場輸出 UTF-8 CSV。

程式不使用私人 API key，不登入帳戶，也不執行下單或放貸。

## 環境需求

- Python 3.11 以上
- 可連線至 `https://api-pub.bitfinex.com`

## 安裝

在專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

## 測試

預設測試完全不使用網路：

```powershell
python -m pytest -v
```

明確執行 Bitfinex 真實 API smoke test：

```powershell
python -m pytest -m integration tests/integration/test_live_api.py -v
```

## 執行資料收集

```powershell
python -m bitfinex_lending
```

預設輸出：

- SQLite：`data/bitfinex_lending.sqlite3`
- CSV：`data/csv/`

退出碼：

- `0`：三個市場都成功，或 API 成功但其中有空資料警告。
- `1`：至少一個市場失敗，或 SQLite 無法初始化／寫入。

單一市場失敗不會阻止其他市場繼續執行。終端摘要會顯示 `run_id`、各市場狀態、資料筆數及成功／空資料／失敗總數。

## Windows 工作排程器

建立「基本工作」後設定：

- 程式或指令碼：`D:\nSchool教育課程\Bitfinex_landing\.venv\Scripts\python.exe`
- 新增引數：`-m bitfinex_lending`
- 開始位置：`D:\nSchool教育課程\Bitfinex_landing`

建議先在 PowerShell 手動執行同一命令，確認網路、SQLite 與 CSV 路徑均正常，再啟用排程。

## 資料欄位

快照 CSV 欄位順序：

```text
run_id,market,rate,period,count,amount,side,fetched_at
```

## 建模特徵資料集

先完成至少一次資料收集，再執行：

```powershell
python -m bitfinex_lending.features
```

這個指令會從 SQLite 的 `funding_book_snapshots` 重新計算全部特徵，以單一交易更新 `modeling_features` 資料表，並輸出 UTF-8 CSV：

- SQLite：`data/bitfinex_lending.sqlite3`
- CSV：`data/csv/modeling_features.csv`

每次執行都是完整重建，不會追加重複資料。第一個觀測時間的前期差分欄位為空值；最後一個觀測時間的下期目標為空值。若原始資料為空，指令仍會成功並產生只含標頭的 CSV。

目前的歷史快照數量仍少，這份資料集適合驗證管線，不足以支撐可靠的模型訓練或決策建議。

所有時間均使用帶有 UTC offset 的 ISO 8601 格式。`amount > 0` 記為 `offer`，`amount < 0` 記為 `demand`。

## GitHub Actions 每小時自動收集

Repository 使用 `.github/workflows/collect-funding-books.yml`，在每小時第 17 分鐘（UTC）抓取 `fUSD`、`fBTC`、`fETH`，也可從 GitHub 的 **Actions → Collect Bitfinex funding books → Run workflow** 手動執行。

資料依 UTC 日期追加到：

```text
data/raw/YYYY/MM/DD/fUSD.csv
data/raw/YYYY/MM/DD/fBTC.csv
data/raw/YYYY/MM/DD/fETH.csv
```

啟用步驟：

1. 將 repository 設為 private 並推送 default branch。
2. 到 **Settings → Actions → General → Workflow permissions**，允許 **Read and write permissions**。
3. 到 Actions 頁面手動執行一次 workflow。
4. 確認工作完成後出現 `data: collect funding books ... [skip ci]` commit。
5. 再執行一次，確認當日 CSV 追加資料且只有一列標頭。

workflow 使用 Bitfinex public endpoint，不需要 API key 或 GitHub secret。private repository 的 GitHub Free 帳戶目前包含每月 Actions 分鐘額度；此排程約執行 720 次/月，仍應每月從 **Settings → Billing and licensing** 檢查實際用量。

GitHub scheduled workflow 可能延遲，資料時間以 CSV 的 `fetched_at` 為準。SQLite 是 runner 內的暫存記錄，不會提交；可在分析環境由 repo 中的 CSV 重建資料庫。
