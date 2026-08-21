# P0 業師建議版執行清單

最後更新：2026-08-22

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

- [ ] Task 1：將 `fUST` 納入 funding-book 原始資料收集
- [ ] Task 2：實作官方按秒計息、15% 手續費與 1,000 單位拆單規則
- [ ] Task 3：建立公開市場小時資料標準化與新版 60 天資料門檻
- [ ] Task 4：建立五個利率分位點、成交機率、等待時間與容量統計
- [ ] Task 5：建立 1,000～10,000 USDT 拆單、複利與組合最佳化
- [ ] Task 6：建立 walk-forward、三種簡單基準及有／無預測模型比較
- [ ] Task 7：原子輸出 Markdown、CSV、JSON、狀態與保留上一版結果
- [ ] Task 8：建立本機唯讀互動介面
- [ ] Task 9：建立每日台灣時間 10:00 分析管線與排程
- [ ] Task 10：執行 production path、完整測試、隱私檢查及文件交接

## C. 正式資料成熟度（與功能完成分開）

- [ ] USDT 公開資料連續涵蓋至少 60 天
- [ ] 每小時資料完整率至少 90%
- [ ] 最長公開資料缺口不超過 6 小時
- [ ] 每個「利率分位點 × 期限 × 等待時間」組合至少有 30 次可驗證機會
- [ ] BTC 資料達相同門檻，否則保持 `insufficient_data`
- [ ] ETH 資料達相同門檻，否則保持 `insufficient_data`

> 功能可以在資料累積期間先完成。C 節未全部通過時，介面與報告只能顯示「實驗結果／資料不足」，不得宣稱正式最佳策略。

## D. 下一次續作入口

1. 從實作計畫 Task 1 開始，以 TDD 完成 `fUST` funding-book 收集。
2. 每完成一個 Task，執行該 Task 的 focused tests 並獨立提交。
3. 不因資料尚未滿 60 天而停止功能實作。
4. 不得跳過 Task 7 的 last-good 與隱私保護後直接啟用每日排程。
