# 本機公開資料 GitHub 同步

本功能把本機公開 Bitfinex 資料同步至 GitHub 預設主分支，供業師查核。GitHub Actions 資料維持在 `data/raw/`；本機公開資料使用 `data/local_public/raw/` 與 `data/local_public/market/`。私人資料 `data/account/`、憑證及私人狀態永不納入同步。

## 手動預覽與同步

預覽只檢查白名單、檔案數與資料量，不連線或推送：

```powershell
python -m bitfinex_lending.public_git_sync --project-root . --branch master
```

確認後才執行推送：

```powershell
python -m bitfinex_lending.public_git_sync --project-root . --branch master --push
```

結果為 `success`、`no_changes` 或 `failed`。本機狀態寫入 `data/metadata/public_git_sync_status.json`，此檔不進 Git。同步失敗時，狀態檔會記錄失敗階段、Git 回傳碼（若有）與實際推送嘗試次數；不保存完整命令、遠端網址或錯誤輸出，避免憑證資訊外洩。同步失敗不會刪除公開資料，也不會停止公開或私人收集器。

## 每週排程

先預覽排程設定：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-public-github-sync.ps1 -ProjectRoot .
```

確認後註冊並啟用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-public-github-sync.ps1 -ProjectRoot . -Enable
```

工作名稱為 `BitfinexPublicGitHubSync`，每週一台灣本機時間 10:00 執行。若當時關機，Windows 會在下次可執行時補跑；同一時間只允許一個實例，執行上限 30 分鐘。

## 安全限制

- 每週工作只同步 `data/local_public/raw/`、`market/` 與公開 metadata。
- 程式碼及一般文件不由每週工作自動提交，必須人工審查。
- 不使用 `git add .`，不保存新的明文 GitHub Token。
- 系統唯讀分析資料，不會提交、修改或取消 Bitfinex 訂單。
- GitHub 與本機公開原始資料仍分開保存，只在模型載入階段依下列規則合併。

## 模型層合併規則

- 以「市場＋UTC 小時」為選取單位，每小時只採用一個完整 funding-book 快照。
- 同一小時有本機資料時優先採用本機來源；本機缺少時才由 GitHub `data/raw/` 補入。
- 同一來源同一小時若有多次有效快照，採用該小時時間最晚的一次；不同快照的 order-book 資料列不互相混合。
- 原始 CSV 不會被合併或覆寫；候選、採用、重疊及捨棄數量寫入 `data/modeling/source_merge_status.json`，不包含原始資料列、run ID 或本機路徑。
