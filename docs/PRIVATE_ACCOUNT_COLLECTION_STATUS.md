# 私有 Funding 資料收集狀態

最後更新：2026-08-24

## 目前狀態

- 私有 API Key 已建立，僅使用 Funding/History 的唯讀權限。
- `--dry-run` 權限檢查成功。
- 手動私有資料收集成功。
- Windows 工作排程 `BitfinexPrivateAccountCollector` 已建立並啟用。
- 排程頻率：每 5 分鐘。
- 手動啟動排程後，Metadata 狀態為 `success`。
- 公開與私人 CSV 已改為 UTC 每日分檔；私人排程持續累積真實資料。
- 私人資料不進 Git，只有收集器程式、測試、排程與說明文件可以同步。

## 第一次成功收集結果

來源檔案：`data/metadata/account_collector_status.json`

```text
funding_offers  : 1
funding_trades  : 25
funding_loans   : 1
funding_credits : 1
failures        : 0
status          : success
```

## 私有資料位置

```text
data/account/
  funding_offers/YYYY/MM/DD.csv
  funding_trades/YYYY/MM/DD.csv
  funding_loans/YYYY/MM/DD.csv
  funding_credits/YYYY/MM/DD.csv
  account_events.sqlite3

data/metadata/account_collector_status.json
```

私有資料只保存在本機，不同步到 GitHub。

## 後續執行順序

### 階段 1：確認收集穩定性

- [x] 連續執行超過 24 小時。
- [x] 確認排程沒有持續性的權限錯誤或 nonce 錯誤。
- [x] 確認 Offers、Trades 與 Loans 資料持續更新；Credits 沒有新事件時不要求檔案時間變動。

### 階段 2：建立資料品質報告

- [ ] 統計每小時成功收集次數。
- [ ] 統計四類資料的筆數與空結果次數。
- [ ] 檢查重複事件與缺漏時間區間。
- [ ] 計算 API 失敗率與排程成功率。

### 階段 3：開始初步回測

- [ ] 資料品質達可用門檻後，以私人資料校正公開市場成交代理。
- [ ] 以 UTC 時間對齊 `data/market/` 與 `data/account/`。
- [ ] 比較不同利率、放貸天數與成交率。
- [ ] 以 1,000～10,000 USDT、每份 1,000 USDT 拆單計算。

### 階段 4：提高可靠度

- [ ] 收集 14～30 天資料。
- [ ] 比較不同時間區間的回測結果是否一致。
- [ ] 產生利息、成交率、閒置時間、資金使用率與本金加利息總額報告。
- [ ] 在樣本數足夠前，不宣稱任何策略為最佳策略。

## 回測啟動條件

在以下條件達成前，暫不進行正式策略結論：

- 至少 7 天連續資料。
- 排程成功率與資料缺漏已完成檢查。
- Funding Trades 與 Loans 有足夠的實際事件樣本。
- 公開市場資料與私人資料可以依時間對齊。
