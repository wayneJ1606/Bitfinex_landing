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
