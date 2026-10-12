# P0 業師建議版執行清單

最後更新：2026-10-12

本文件是 P0 的可勾選進度入口。需求與完成定義以 [`P0 放貸策略最佳化設計`](superpowers/specs/2026-08-19-p0-funding-strategy-optimizer-design.md) 為準；逐檔案、逐測試的執行順序以 [`P0 Funding Strategy Optimizer Implementation Plan`](superpowers/plans/2026-08-22-p0-funding-strategy-optimizer.md) 為準。`todo.md` 只維護上層目標，`progress.md` 只新增已驗證里程碑。

## A. 已完成的前置工作

- [x] 公開市場與私人帳戶唯讀收集器持續運作
- [x] 公開與私人 CSV 改為 UTC 每日分檔
- [x] 建立掛單生命週期表
- [x] 建立 Offers History／Funding Trades 配對稽核
- [x] 建立公開／私人資料 UTC 對齊工具
- [x] 建立 B1／B2 基準定義框架
- [x] 完成新版 P0 需求訪談與設計核准
- [x] 建立新版逐任務實作計畫

## B. 功能實作順序

- [x] Task 1：將 `fUST` 納入 funding-book 原始資料收集
- [x] Task 2：實作官方按秒計息、15% 手續費與 1,000 單位拆單規則（commit `a2a0c5e`；30 tests passed）
- [x] Task 3：建立公開市場小時資料標準化與新版 60 天資料門檻（commits `3ab21f6`、`f3044a5`）
- [x] Task 4：建立五個利率分位點、成交機率、等待時間與容量統計（commit `dc29672`；9 focused tests passed）
- [x] Task 5：建立 1,000～10,000 USDT 拆單、複利與組合最佳化（commit `4f0a833`；13 focused tests passed）
- [x] Task 6：建立 walk-forward、三種簡單基準及有／無預測模型比較（commit `d55ae41`；16 focused tests passed）
- [x] Task 7：原子輸出 Markdown、CSV、JSON、狀態與保留上一版結果（commit `51dd586`；8 focused tests passed）
- [x] Task 8：建立讀取 Task 7 統一結果的正式本機唯讀互動介面（commit `55c0b0a`；13 focused integration tests passed）
- [x] Task 9：建立每日台灣時間 10:00 分析管線與排程（Task 9A commit `23fbc3c`；Task 9B commit `c6e54e1`；合併後 `367 passed, 1 deselected`；排程手動驗收 `LastTaskResult=0`）
- [x] Task 10：執行 production path、完整測試、隱私檢查及文件交接（production status `experimental`；跨格式抽查一致；敏感詞無命中；`367 passed, 1 deselected`）

## C. 正式資料成熟度（與功能完成分開）

- [ ] USDT 公開資料連續涵蓋至少 60 天
- [ ] 每小時資料完整率至少 90%
- [ ] 最長公開資料缺口不超過 6 小時
- [ ] 每個「利率分位點 × 期限 × 等待時間」組合至少有 30 次可驗證機會
- [ ] BTC 資料達相同門檻，否則保持 `insufficient_data`
- [ ] ETH 資料達相同門檻，否則保持 `insufficient_data`

> 功能可以在資料累積期間先完成。C 節未全部通過時，介面與報告只能顯示「實驗結果／資料不足」，不得宣稱正式最佳策略。

截至 2026-10-12，USDT 有 1,187 個完整每小時觀測，跨度 1,186 小時（約 49.4 天），完整率 100%、最大缺口 1 小時，每策略至少有 1,163 次觀察機會。目前仍未達 60 天門檻，因此產物繼續標示 `experimental`，不宣稱正式最佳策略。

## D. 下一次續作入口

1. 繼續每日產生實驗結果，並在 USDT 連續歷史達 60 天後重跑 production path 與 walk-forward 驗證。
2. 目前有效歷史起點為 2026-08-24 02:00 UTC；若後續不中斷，下一個 60 天檢查點為 2026-10-23 02:00 UTC（台灣時間 10:00）。
3. 不因資料尚未滿 60 天而停止文件與結案報告整理；正式策略結論仍須等待 C 節門檻。
4. 下一階段可進入結案報告修正與 Git 成果整理，但仍要把正式資料成熟度與功能完成度分開記錄。
