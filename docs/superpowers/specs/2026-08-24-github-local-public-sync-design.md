# GitHub 與本機公開資料分流同步設計

日期：2026-08-24
狀態：使用者已確認設計，尚未實作

## 1. 目的

將目前留在本機的公開收集資料、收集器實作、實驗模型／Dashboard，以及 `progress.md`、`todo.md` 與其關聯文件安全同步到 GitHub 預設主分支，供業師查核。同時保證 Bitfinex 私人帳戶資料、憑證及可識別交易紀錄只留在本機。

本設計只處理「來源分流與安全同步」。GitHub 與本機公開資料的去重、衝突判定及模型層合併留待後續獨立設計。

## 2. 已確認的範圍

### 必須同步

- 2026-08-16 起的本機公開 funding-book 原始資料。
- 本機公開 ticker、funding statistics、funding candles 與價格資料。
- GitHub Actions funding-book 收集器與本機公開市場收集器的程式、排程腳本、測試及操作文件。
- 私人唯讀收集器的程式、排程腳本、測試、`.env.example` 及不含真實帳戶內容的操作文件。
- 已建立安全提交的實驗模型與 Dashboard 程式、測試，以及通過隱私檢查的最新展示成果。
- `progress.md`、`todo.md`，以及兩者連結的專案方向、目標、P0 規格、實作計畫、檢查清單與相關操作文件。

### 永不自動同步

- `.env`、API Key、API Secret 或任何真實憑證。
- `data/account/` 下的 SQLite、CSV 及其他私人帳戶資料。
- 私人收集狀態、私人 collector run history、完整 offer／trade／loan／credit 識別碼及原始私人 payload。
- 本機 lock、log、暫存檔、資料庫 journal 或其他執行期檔案。
- 未列入白名單的未提交程式、文件或資料。

## 3. 資料來源分流

採用保留 GitHub 既有路徑、另建本機公開資料區的方案：

```text
data/raw/                    GitHub Actions 公開 funding-book 歷史資料
data/local_public/raw/       本機公開 funding-book 資料
data/local_public/market/    本機 ticker、stats、candles、prices
data/local_public/metadata/  可公開的同步清單、時間與筆數摘要
data/account/                私人帳戶資料，永久留在本機
data/metadata/               本機執行狀態，預設不整包同步
```

`data/raw/` 的現有 GitHub 歷史與 workflow 不搬移，降低破壞既有自動收集的風險。本機公開收集器完成切換後，只寫入 `data/local_public/`，兩個來源不再共同修改同一個 CSV。

同步清單只能包含公開統計，例如同步時間、資料日期範圍、檔案數、列數、雜湊及成功／失敗狀態，不得包含帳戶或交易識別資訊。

## 4. 第一次安全同步

1. 在獨立 Git 工作區取得 GitHub 預設主分支最新內容，不直接使用目前含大量未提交變更的開發工作區推送。
2. 將 2026-08-16 起的本機公開 `data/raw/` 複製到 `data/local_public/raw/`，並將現有 `data/market/` 複製到 `data/local_public/market/`。
3. 逐檔核對來源與新位置的檔案數、列數、大小及內容雜湊。核對成功前不得刪除或覆寫來源。
4. 修改本機公開收集器的未來輸出位置，並以測試與一次受控收集確認只寫入新路徑。
5. 分批審查並提交：公開收集器、私人唯讀收集器、實驗模型／Dashboard、進度與關聯文件、公開資料。
6. 每批只用明確檔案白名單加入 Git，禁止使用 `git add .` 或涵蓋整個 `data/` 的加入方式。
7. 在推送前重新取得遠端主分支並整合最新 GitHub Actions 資料；完成測試、隱私掃描與 staged diff 審查後才推送。

## 5. 每週自動同步

- Windows 排程於每週一台灣時間 10:00 執行。
- 設定 `StartWhenAvailable`；若電腦關機或當時無法執行，下一次可用時補跑。
- 本機每小時公開／私人收集排程保持獨立，GitHub 同步失敗不得阻止資料收集。
- 排程使用隔離的同步工作區，只複製並加入：
  - `data/local_public/raw/`
  - `data/local_public/market/`
  - `data/local_public/metadata/` 中核准的公開同步清單
- 同一份資料以穩定路徑與內容雜湊去重；沒有新內容時不建立空提交。
- 推送前執行 fetch／rebase；若遠端因 GitHub Actions 更新而前進，進行有限次數重試。超過上限後保留本機資料並記錄失敗，下一次排程可重試。
- 自動同步不得提交程式碼、一般文件或白名單外的工作區變更；這些內容只能經人工審查後同步。

## 6. 程式與文件同步規則

第一次同步須讓業師能從主分支完整追查目前成果，而不是只看到資料：

- 公開 funding-book 與 market 收集流程、資料路徑及排程說明必須一致。
- 私人收集器程式可公開，但文件只提供環境變數名稱、最低唯讀權限與操作方式，不包含真實值或私人輸出範例。
- `progress.md` 與 `todo.md` 的相對連結必須在 GitHub 上可開啟；同步前檢查其直接關聯文件是否存在並納入同一批或較早的提交。
- 實驗 Dashboard 必須保留「非常低可信度實驗值」、資料不足、不構成投資建議及不自動下單等限制。
- 最新展示成果只發布經欄位白名單與敏感字串掃描確認的靜態輸出，不發布完整私人校正資料。

## 7. 安全與失敗處理

- `.gitignore` 必須持續排除 `data/account/`、私人 metadata、憑證、SQLite、log、lock 與暫存檔。
- 同步前同時做路徑白名單、Git staged 檔案清單及內容敏感字串掃描；任何一項失敗即停止提交與推送。
- 推送失敗不回滾、不刪除本機公開資料，也不影響公開或私人收集器。
- 不自動解決同一檔案的內容衝突；因本設計已分流來源，出現同檔衝突應視為設定錯誤並停止。
- 自動排程只使用目前登入者的必要權限與既有 Git 認證，不保存新的明文 GitHub Token。

## 8. 驗證與完成條件

完成實作前必須驗證：

1. 2026-08-16 起的本機公開資料在新路徑與來源逐檔一致。
2. GitHub Actions 仍只寫入 `data/raw/`，本機公開收集器只寫入 `data/local_public/`。
3. 私人收集器仍只寫入本機 `data/account/` 與私人 metadata。
4. 週一 10:00 排程可預覽、啟用、補跑、無新資料跳過及失敗後重試。
5. 自動同步 staged 清單只含三個核准的 `data/local_public/` 子路徑。
6. GitHub 主分支可開啟 `progress.md`、`todo.md` 及其關聯文件，並可查看收集器與實驗 Dashboard 成果。
7. Git 歷史與發布內容找不到憑證、`data/account/`、私人狀態、私人識別碼或原始私人 payload。
8. 完整離線測試通過，且未破壞既有 GitHub Actions、本機公開收集及私人唯讀收集排程。

## 9. 非本階段範圍

- 合併 GitHub 與本機公開資料成單一訓練資料集。
- 自動判斷兩來源同時間資料何者優先。
- 將私人帳戶資料匿名化後上傳。
- Git LFS、外部物件儲存或資料庫服務；目前約 2 MiB／週的公開資料量尚不需要這些機制。
- 自動下單、修改 Bitfinex 帳戶或提高私人 API 權限。
