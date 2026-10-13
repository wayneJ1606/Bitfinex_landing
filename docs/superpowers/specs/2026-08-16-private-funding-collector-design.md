# 私有 Funding 唯讀資料收集器設計

## 目標

建立一個只讀取使用者本人 Bitfinex Funding 資料的本機收集器，供後續分析放貸利率、成交率、放貸期間與收益使用。

## 明確範圍

第一版只收集 Funding 相關資料：

- 目前進行中的 Funding Offers
- Funding Trades
- Funding Loans
- Funding Credits

不收集錢包餘額、Ledger、交易市場資料，也不推送私有資料到 GitHub。

## API 權限與安全

使用獨立的 Bitfinex API Key，僅開啟：

- `funding: READ`
- `history: READ`

所有 WRITE 權限、下單、撤單、提領、轉帳與設定修改權限都必須關閉。程式啟動時先呼叫權限檢查端點；若發現 WRITE 權限或非預期權限，立即停止。

API Secret 只從本機環境變數或 Windows Credential Manager 讀取，不寫入程式碼、CSV、Metadata、GitHub 或日誌。單一收集程序使用該 API Key，以避免 Bitfinex nonce 不遞增。

## 架構

私有收集器與公開市場收集器分離，使用獨立 Windows 工作排程：

```text
BitfinexPrivateAccountCollector
    -> permission check
    -> authenticated read-only requests
    -> local account storage
    -> status metadata and redacted log
```

預設每 5 分鐘執行一次；同一排程不允許重複執行。連線失敗使用有限次數重試與退避，不因單一端點失敗而執行任何替代寫入操作。

## 儲存格式

```text
data/account/
  funding_offers.csv
  funding_trades.csv
  funding_loans.csv
  funding_credits.csv
  account_events.sqlite3

data/metadata/
  account_collector_status.json
```

每筆資料保留來源端點、收集時間、Bitfinex 原始時間、資料識別碼與 schema 版本。寫入採可重複執行方式，以 Bitfinex 識別碼去重，不覆蓋已存在的歷史事件。

## 錯誤處理

- 權限檢查失敗：停止本次執行並記錄原因。
- 發現 WRITE 權限：停止本次執行並產生高優先級警告。
- 單一端點失敗：保留其他端點成功結果，於 Metadata 記錄失敗端點。
- API 限流或網路錯誤：有限次數重試，超過上限後結束本次排程。
- Secret 缺失：不發送任何 authenticated request，直接停止。

## 驗證與完成條件

1. 單元測試確認所有私有請求只使用允許的 Funding/History 端點。
2. 測試確認不存在下單、撤單、轉帳與提領呼叫。
3. 使用測試帳戶權限檢查成功，且 Secret 不出現在輸出與日誌。
4. 手動執行一次唯讀收集，四類資料可寫入或明確記錄無資料。
5. 啟用獨立排程後，連續觀察至少 24 小時，確認無重複執行與 nonce 錯誤。

## 非目標

- 不建立交易策略或自動放貸策略。
- 不執行任何帳戶狀態變更。
- 不把私有資料同步到 GitHub。
- 不在第一版加入錢包餘額、Ledger 或市場預測。
