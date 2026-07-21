# GitHub Actions 自動資料收集設計

## 目標

使用 GitHub Actions 在 private repository 中每小時執行一次 Bitfinex public funding book 資料收集，不依賴本機電腦持續開機。成功取得的 `fUSD`、`fBTC`、`fETH` 快照應追加至按日期及市場分割的 CSV，並由 workflow 自動提交回 repository。

本階段只建立可靠的資料收集與保存流程，不執行模型訓練、回測或自動交易。

## 排程與額度

- 使用 GitHub-hosted `ubuntu-latest` runner。
- 以 cron 在每小時第 17 分鐘執行，避開整點高負載時段。
- 提供 `workflow_dispatch`，允許從 GitHub Actions 頁面手動測試。
- 使用 private repository 的 GitHub Actions 免費分鐘；預估每月約 720 次工作，目標是讓每次工作在一個計費分鐘左右完成。
- 設定 workflow `concurrency`，同一時間只允許一個收集工作，避免重複寫入。
- 接受 scheduled workflow 可能延遲；資料時間以實際 `fetched_at` 為準，不假設整點準時執行。

## 資料儲存格式

每日為每個市場保存一個 CSV：

```text
data/raw/YYYY/MM/DD/fUSD.csv
data/raw/YYYY/MM/DD/fBTC.csv
data/raw/YYYY/MM/DD/fETH.csv
```

欄位沿用目前快照格式：

```text
run_id,market,rate,period,count,amount,side,fetched_at
```

每次市場快照可能包含多個 funding book rows；workflow 將整批 rows 追加到當日該市場檔案。`run_id` 識別同一次三市場收集，`fetched_at` 記錄各市場實際取得資料的時間。

CSV 使用 UTF-8、固定欄位順序與單一標頭。首次寫入當日檔案時建立標頭；後續執行只追加資料列，不重複標頭。

## 執行流程

1. Checkout default branch 的最新版本。
2. 安裝專案要求的 Python 版本與套件。
3. 建立本次 `run_id`，依序向 Bitfinex public books endpoint 取得三個市場資料。
4. 沿用現有 parser 驗證 API rows，並沿用既有錯誤分類。
5. 將各個成功市場的資料追加到對應每日 CSV。
6. 檢查工作樹；只有 CSV 確實變更時才建立自動 commit。
7. 在 push 前同步遠端最新狀態，再將 commit 推送至 default branch。

workflow commit message 使用固定前綴並包含 UTC 收集時間，例如：

```text
data: collect funding books at 2026-07-21T13:17Z [skip ci]
```

## 程式邊界

- 現有 HTTP client 與 parser 保持單一職責，不處理 Git 或 workflow 細節。
- 新增每日 CSV writer，負責路徑選擇、標頭、追加及同一 `run_id` 去重。
- runner/CLI 協調三市場收集，並以執行結果決定成功或失敗狀態。
- Git checkout、commit 與 push 只存在 workflow，不放入 Python 應用程式。
- SQLite 保留供本機分析或未來由 CSV 重建；GitHub 每小時排程不提交 SQLite，避免二進位 Git 歷史膨脹。

## 失敗處理與資料一致性

- 單一市場失敗時繼續其他市場；成功市場仍可保存。
- 全部市場失敗時，不改動 CSV、不 commit，workflow 回報失敗。
- 部分市場失敗時，保存成功資料，但 workflow 回報非成功，讓 GitHub 通知可見。
- 寫入前先在暫存檔建立新內容，再以原子替換更新每日 CSV，避免程序中止留下半行或損壞檔案。
- 同一 `run_id` 已存在於目標檔案時不再追加，以便 workflow retry 不產生重複快照。
- 既有 CSV 不會因 API 失敗而被清空或覆蓋。
- 若 push 因遠端更新發生衝突，workflow 重新同步後重試一次；仍失敗時保留 Actions log 並回報失敗，不強制覆寫遠端。

## GitHub 權限與安全

- Bitfinex public endpoint 不需要 API key，不建立交易所 secret。
- workflow 明確宣告最小權限 `contents: write`，使用 GitHub 自動提供且短期有效的 `GITHUB_TOKEN`。
- 不使用 personal access token。
- repository 的 Actions 設定需允許 workflow 讀寫內容；若 default branch 有保護規則，需允許 GitHub Actions bot 寫入或改採 pull request 流程。
- 系統只讀取公開行情，不使用私人帳戶、不下單、不執行放貸。

## 測試與驗收

單元測試應覆蓋：

- 新日期／新市場檔案會建立一次標頭。
- 同日後續快照只追加資料列。
- 不同日期與市場寫入不同路徑。
- 相同 `run_id` retry 不重複追加。
- parser 或 API 失敗不破壞既有檔案。
- 路徑與時間一律依 UTC 計算。

整合驗收：

1. 既有非 integration 測試全部通過。
2. 本機以暫存目錄執行收集流程，確認三個每日 CSV 格式正確。
3. 推送 workflow 後先以 `workflow_dispatch` 手動執行。
4. 確認 Actions 工作成功、自動 commit 出現且包含三市場資料。
5. 再次手動執行，確認檔案追加而非覆蓋，且沒有重複標頭。
6. 觀察至少一次 scheduled run，確認 cron、權限與 push 均正常。

## 不在本階段範圍

- 模型訓練、模型評估與回測。
- GitHub Artifact 作為主要資料庫。
- 獨立 `data` branch。
- 每小時提交 SQLite 或建模特徵 CSV。
- 自動修補長時間缺漏的歷史時段。
- 任何私人 API 或真實交易操作。

## 後續維護

- 每月檢查 GitHub Actions 使用分鐘數與失敗率。
- 每季檢查 repository 大小與 commit 增長；如歷史開始影響 clone 或分析，再評估每日批次 commit、獨立 data branch 或外部物件儲存。
- 未來可另建每日驗證工作，檢查 CSV schema、重複 `run_id`、缺漏時段與異常檔案，但不納入第一版排程。
