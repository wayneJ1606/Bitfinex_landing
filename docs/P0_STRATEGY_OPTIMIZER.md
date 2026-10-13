# P0 放貸策略分析操作說明

本工具讀取本機既有的公開市場資料與可選的私人衍生統計，產生 P0 策略比較結果。它不呼叫 Bitfinex 私有寫入 API、不會建立或取消掛單，也不會自動投資。

## 手動更新

在專案根目錄執行：

```powershell
python -m bitfinex_lending.p0_strategy_pipeline
```

成功後會更新：

- `data/modeling/p0_strategy/latest/dashboard.html`：本機唯讀 Dashboard。
- `data/modeling/p0_strategy/latest/report.md`：策略比較報告。
- `data/modeling/p0_strategy/latest/strategy_results.csv`：完整策略結果。
- `data/modeling/p0_strategy/latest/dashboard_data.json`：Dashboard 資料。
- `data/modeling/p0_strategy/latest/status.json`：本次發布狀態。
- `data/modeling/p0_strategy/strategy_coverage.csv`：各策略可驗證機會統計。
- `data/metadata/p0_strategy_status.json`：最近一次執行狀態與最後成功時間。

所有正式輸出會整組更新；若其中一步失敗，上一個成功的 `latest` 版本會保留。

## 每日 10:00 排程

先預覽，不會註冊工作：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-p0-strategy-analysis.ps1 -ProjectRoot .
```

確認預覽內容後，才以 `-Enable` 註冊並啟用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-p0-strategy-analysis.ps1 -ProjectRoot . -Enable
```

排程名稱是 `BitfinexP0StrategyAnalysis`，每天依 Windows 本機時間 10:00 執行。它使用 `pythonw.exe` 靜默運行、同一時間只允許一個實例、錯過時間後可補跑，單次最長執行 30 分鐘。電腦關機時不會執行，之後開機且使用者登入時由 Windows 依 `StartWhenAvailable` 規則補跑。

## 狀態說明

- `formal`：公開資料已通過正式門檻，可以作為正式回測結果；仍不是保證收益或投資建議。
- `experimental`：已產生策略結果，但資料成熟度尚未通過正式門檻，只能作為研究參考。
- `insufficient_data`：可用資料不足，無法產生足夠的策略結果，或正式成熟度判定仍不足。
- `failed`：最近一次分析失敗；系統保留上一個成功版本，錯誤摘要記錄於 metadata 狀態檔。
- `stale`：Dashboard 判定最後成功更新超過 48 小時，畫面會提示資料可能過期。

正式門檻仍是 USDT 公開資料連續涵蓋至少 60 天、每小時完整率至少 90%、最長缺口不超過 6 小時，且每個策略組合至少有 30 次可驗證機會。
