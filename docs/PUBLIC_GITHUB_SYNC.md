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

結果為 `success`、`no_changes` 或 `failed`。本機狀態寫入 `data/metadata/public_git_sync_status.json`，此檔不進 Git。同步失敗不會刪除公開資料，也不會停止公開或私人收集器。

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
- GitHub 與本機公開資料目前只分開保存，尚未合併成單一訓練資料集。
