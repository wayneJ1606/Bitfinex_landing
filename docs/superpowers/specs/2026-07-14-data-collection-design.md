# Bitfinex 放貸資料收集版本設計

## 目標

建立可由 Windows 工作排程器呼叫的單次執行程式，依序抓取 Bitfinex `fUSD`、`fBTC`、`fETH` funding book，解析後寫入 SQLite、輸出快照 CSV，並保留每輪執行與錯誤紀錄。

本階段只處理資料收集與持久化，不包含常駐排程、特徵工程、建模、回測、私人 API、下單或放貸操作。

## 技術選擇

- Python 3.11 以上。
- `requests`：呼叫 Bitfinex Public Books API。
- Python 標準函式庫：`sqlite3`、`csv`、`logging`、`dataclasses`、`pathlib`。
- `pytest`：自動化測試。
- Windows 工作排程器負責定時呼叫；Python 程式本身每次只執行一輪。

## 執行介面

主要執行方式：

```powershell
python -m bitfinex_lending
```

每輪建立唯一 `run_id`，依序處理三個 markets。全部成功時退出碼為 `0`；至少一個 market 失敗時退出碼為 `1`。單一 market 失敗不阻止後續 markets 執行。

## 架構與責任

```text
Windows 工作排程器
        ↓
單次執行入口
        ↓
Bitfinex API Client
        ↓
Funding Book Parser
        ↓
┌──────────────┬──────────────┐
│ SQLite 儲存  │ 快照 CSV 輸出 │
└──────────────┴──────────────┘
        ↓
執行摘要與退出碼
```

- `config.py`：三個 markets、API base URL、book precision、資料筆數、HTTP timeout、SQLite 與 CSV 路徑。
- `client.py`：送出 HTTP GET 並回傳已解碼的 JSON；不負責解析業務欄位或儲存。
- `models.py`：定義 funding book row 與 market 抓取結果的資料結構。
- `parser.py`：驗證每列 `[rate, period, count, amount]`，轉換型別並依 `amount` 正負值產生 `side`。
- `storage.py`：建立 schema，以 transaction 寫入 funding book snapshots、crawl logs 與 error logs。
- `csv_export.py`：將單一 market 的成功快照原子化輸出成 UTF-8 CSV。
- `runner.py`：建立 `run_id` 與 UTC 抓取時間，協調三個 markets，彙整成功、空資料與失敗結果。
- `__main__.py`：組裝正式元件、輸出摘要並回傳退出碼。

各模組透過明確函式或資料物件溝通，不直接讀取其他模組的內部狀態。

## API 與解析規則

API 路徑格式：

```text
https://api-pub.bitfinex.com/v2/book/{market}/P0?len=25
```

每列預期格式為 `[rate, period, count, amount]`：

- `rate`：浮點數。
- `period`：整數。
- `count`：整數。
- `amount`：浮點數。
- `side`：`amount > 0` 為 `offer`，`amount < 0` 為 `demand`。
- `amount == 0` 視為無效資料列，整個 market 解析失敗，避免建立方向不明的快照。
- `fetched_at`：該 market 開始抓取時建立的 UTC ISO 8601 時間。

任何資料列欄位數錯誤、型別錯誤或方向無法判斷時，整個 market 不寫入 snapshots，也不輸出 CSV。

## SQLite 資料

SQLite 至少包含下列表格：

### `funding_book_snapshots`

- `id`：自增主鍵。
- `run_id`：本輪執行識別碼。
- `market`、`rate`、`period`、`count`、`amount`、`side`、`fetched_at`。

### `crawl_logs`

- `id`：自增主鍵。
- `run_id`、`market`、`started_at`、`finished_at`。
- `status`：`success`、`empty` 或 `failed`。
- `row_count`：成功解析列數。
- `message`：可讀摘要。

### `error_logs`

- `id`：自增主鍵。
- `run_id`、`market`、`occurred_at`。
- `error_type`：穩定的錯誤分類。
- `message`：不包含憑證或敏感資訊的錯誤摘要。

每個 market 的 snapshots 與 crawl log 使用同一個 transaction 寫入。失敗時只寫入 failed crawl log 與 error log，不留下部分 snapshots。

## CSV 輸出

只為成功且非空的 market 輸出 CSV，欄位為：

```text
run_id,market,rate,period,count,amount,side,fetched_at
```

檔名包含 UTC 時間、market 與 `run_id`，避免排程重複執行時覆蓋。CSV 先寫入同目錄暫存檔，再以原子更名完成；寫入失敗不得留下目標半成品。

空陣列屬於 API 請求成功但資料異常：寫入 `status=empty`、`row_count=0` 的 crawl log，不建立 snapshot、CSV 或 error log，整輪退出碼仍視為成功，但摘要需顯示警告。

## 錯誤處理

下列情況使該 market 失敗：

- HTTP 連線錯誤或 timeout。
- 非 2xx HTTP 回應。
- 無效 JSON。
- JSON 根節點不是陣列。
- 任一資料列格式或型別不符。
- SQLite transaction 失敗。
- CSV 輸出失敗。

失敗需記錄 `crawl_logs` 與 `error_logs`，接著處理下一個 market。若 SQLite 本身無法初始化或無法寫入錯誤紀錄，視為整輪致命錯誤，立即以退出碼 `1` 結束並將訊息輸出至 stderr。

## 測試策略

採用測試先行開發：每個行為先建立失敗測試，確認失敗原因正確，再加入最小實作。

- Parser：有效資料、offer/demand 判斷、零 amount、欄位數與型別錯誤。
- Client：成功 JSON、timeout、連線錯誤、非 2xx 與無效 JSON；HTTP session 由建構參數注入。
- Storage：使用 pytest 臨時目錄中的真實 SQLite，驗證 schema、transaction、成功與失敗紀錄。
- CSV：使用臨時目錄驗證 UTF-8 表頭、資料內容、唯一檔名與不留下暫存檔。
- Runner：使用假的 client 與臨時 SQLite，驗證三市場順序、部分失敗仍繼續、空資料警告及退出碼。
- Smoke test：提供標記為 `integration` 的真實 API 測試，預設測試命令排除，避免一般測試依賴網路。

## 驗收標準

1. `python -m bitfinex_lending` 可依序嘗試抓取 `fUSD`、`fBTC`、`fETH`。
2. 成功資料包含 PRD 指定欄位並保存到 SQLite。
3. 成功且非空的 market 產生可讀取的 UTF-8 CSV。
4. crawl log 能追蹤每個 market 的狀態與資料筆數。
5. 個別 market 失敗時有 error log，且其他 markets 仍會執行。
6. 全成功退出碼為 `0`，任一失敗退出碼為 `1`。
7. 不需要私人 API key，不執行任何帳戶或下單操作。
8. 預設自動化測試不需要網路即可通過。

