# Private Funding Read-Only Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一個只使用 Bitfinex `funding: READ` 與 `history: READ` 權限、定期將本人 Funding 資料保存到本機的收集器。

**Architecture:** 以獨立的 authenticated client 負責 nonce、簽章與唯讀端點白名單；以 account collector 負責抓取、去重、錯誤狀態與本機輸出；以獨立 Windows 工作排程每 5 分鐘執行一次。私有收集器不共用公開市場收集器的 API client、排程或資料目錄。

**Tech Stack:** Python 3.13、requests、SQLite、CSV、PowerShell Windows Task Scheduler、pytest。

## Global Constraints

- 只允許 `funding: READ` 與 `history: READ`；發現 WRITE 或非預期權限時停止。
- 不實作下單、撤單、轉帳、提領或任何帳戶狀態變更端點。
- API Secret 只從本機安全來源讀取，不進入原始碼、CSV、Metadata、GitHub 或日誌。
- 同一 API Key 同時只允許一個 authenticated collector 執行，以確保 nonce 嚴格遞增。
- 私有資料只寫入 `data/account/`，不加入公開資料同步流程。
- 每項工作都必須先有失敗測試，再寫最小實作，再執行該項測試。

---

### Task 1: 建立唯讀 authenticated client 與權限檢查

**Files:**
- Create: `bitfinex_lending/private_client.py`
- Modify: `bitfinex_lending/config.py`
- Create: `tests/test_private_client.py`

**Interfaces:**
- `ReadOnlyBitfinexClient(api_key: str, api_secret: str, session: SessionLike, base_url: str, nonce_factory: Callable[[], str])`
- `check_permissions() -> tuple[dict[str, int], ...]`
- `fetch_private(path: str, payload: dict[str, object]) -> object`
- 允許路徑白名單：`/v2/auth/r/permissions`、`/v2/auth/r/funding/offers`、`/v2/auth/r/funding/trades/hist`、`/v2/auth/r/funding/loans/hist`、`/v2/auth/r/funding/credits`

- [ ] **Step 1: Write failing tests** for nonce increase, Bitfinex signature headers, permission rejection, and forbidden path rejection.
- [ ] **Step 2: Run tests**: `pytest tests/test_private_client.py -q`; expected initial failures for missing client.
- [ ] **Step 3: Implement** POST authentication using a monotonic millisecond nonce, `auth_nonce`, `auth_payload`, and `auth_signature` headers; redact secrets in raised errors.
- [ ] **Step 4: Implement** `check_permissions()` so any permission with a write value or unexpected scope raises `PrivatePermissionError` before data calls.
- [ ] **Step 5: Run tests**: `pytest tests/test_private_client.py -q`; expected PASS.
- [ ] **Step 6: Commit**: `git add bitfinex_lending/private_client.py bitfinex_lending/config.py tests/test_private_client.py && git commit -m "feat: add read-only Bitfinex authenticated client"`.

### Task 2: 建立 Funding 資料正規化與去重儲存

**Files:**
- Create: `bitfinex_lending/account_storage.py`
- Create: `tests/test_account_storage.py`

**Interfaces:**
- `AccountStorage(root: Path)`
- `initialize() -> None`
- `append_snapshot(dataset: str, collected_at: str, rows: Sequence[object]) -> int`
- `write_status(status: dict[str, object]) -> None`

- [ ] **Step 1: Write failing tests** for directory creation, CSV headers, stable event IDs, duplicate suppression, and status JSON.
- [ ] **Step 2: Run**: `pytest tests/test_account_storage.py -q`; expected failures before implementation.
- [ ] **Step 3: Implement** separate CSV files for `funding_offers`, `funding_trades`, `funding_loans`, and `funding_credits`; preserve `source_endpoint`, `collected_at`, Bitfinex timestamp, identifier, raw payload JSON, and `schema_version`.
- [ ] **Step 4: Implement** SQLite `account_events` table keyed by dataset plus Bitfinex identifier, with idempotent insert behavior.
- [ ] **Step 5: Implement** atomic status JSON writes under `data/metadata/account_collector_status.json`.
- [ ] **Step 6: Run**: `pytest tests/test_account_storage.py -q`; expected PASS.
- [ ] **Step 7: Commit**: `git add bitfinex_lending/account_storage.py tests/test_account_storage.py && git commit -m "feat: add private account storage"`.

### Task 3: 建立私有 Funding collector

**Files:**
- Create: `bitfinex_lending/private_account_collector.py`
- Create: `tests/test_private_account_collector.py`

**Interfaces:**
- `run_private_collection(client: ReadOnlyBitfinexClient, storage: AccountStorage, *, collected_at: datetime, max_attempts: int = 3, retry_delay: float = 2.0) -> CollectionSummary`
- `CollectionSummary`: permission status, per-dataset row counts, failures, and completion timestamp.

- [ ] **Step 1: Write failing tests** for permission-first ordering, four allowed datasets, partial endpoint failure, bounded retry, missing credentials, and lock-file single instance behavior.
- [ ] **Step 2: Run**: `pytest tests/test_private_account_collector.py -q`; expected failures.
- [ ] **Step 3: Implement** permission check before any Funding request; fetch only the four allowlisted endpoints.
- [ ] **Step 4: Implement** retry only for network, HTTP 429/5xx, and invalid JSON; never retry or transform an operation into a write request.
- [ ] **Step 5: Implement** redacted logging and status metadata; ensure exceptions never contain the API Secret.
- [ ] **Step 6: Run**: `pytest tests/test_private_account_collector.py -q`; expected PASS.
- [ ] **Step 7: Commit**: `git add bitfinex_lending/private_account_collector.py tests/test_private_account_collector.py && git commit -m "feat: collect private funding data read-only"`.

### Task 4: 加入本機憑證設定與命令列入口

**Files:**
- Modify: `bitfinex_lending/private_account_collector.py`
- Create: `tests/test_private_account_cli.py`
- Create: `docs/PRIVATE_ACCOUNT_COLLECTOR.md`

- [ ] **Step 1: Write failing tests** for environment-variable loading, missing-secret fail-closed behavior, `--dry-run`, and no credential value in logs.
- [ ] **Step 2: Run**: `pytest tests/test_private_account_cli.py -q`; expected failures.
- [ ] **Step 3: Implement** `BITFINEX_READONLY_API_KEY` and `BITFINEX_READONLY_API_SECRET` loading, `--dry-run` permission check, and `python -m bitfinex_lending.private_account_collector` entry point.
- [ ] **Step 4: Document** credential setup, permission checklist, local paths, manual dry-run, and explicit warning never to paste Secret into chat or commit it.
- [ ] **Step 5: Run**: `pytest tests/test_private_account_cli.py -q`; expected PASS.
- [ ] **Step 6: Commit**: `git add bitfinex_lending/private_account_collector.py tests/test_private_account_cli.py docs/PRIVATE_ACCOUNT_COLLECTOR.md && git commit -m "docs: add private collector setup"`.

### Task 5: 建立獨立 Windows 排程（預覽後才啟用）

**Files:**
- Create: `scripts/install-private-account-collector.ps1`
- Create: `tests/test_private_scheduler_script.py`
- Modify: `progress.md`
- Modify: `todo.md`

- [ ] **Step 1: Write failing tests** asserting task name `BitfinexPrivateAccountCollector`, 5-minute trigger, `MultipleInstances=IgnoreNew`, `Interactive` + `Limited`, and no credential literals in the script.
- [ ] **Step 2: Run**: `pytest tests/test_private_scheduler_script.py -q`; expected failures.
- [ ] **Step 3: Implement** preview-by-default PowerShell installer with `-Enable` required to register; task invokes only the private module and uses the project root as working directory.
- [ ] **Step 4: Document** manual dry-run before `-Enable`, disable/remove commands, and separate-task rationale.
- [ ] **Step 5: Run**: `pytest tests/test_private_scheduler_script.py -q`; expected PASS.
- [ ] **Step 6: Commit**: `git add scripts/install-private-account-collector.ps1 tests/test_private_scheduler_script.py progress.md todo.md && git commit -m "feat: add private collector scheduler"`.

### Task 6: 整合驗證與安全檢查

**Files:**
- Modify: `docs/PRIVATE_ACCOUNT_COLLECTOR.md`
- Modify: `progress.md`

- [ ] **Step 1: Run focused tests**: `pytest tests/test_private_client.py tests/test_account_storage.py tests/test_private_account_collector.py tests/test_private_account_cli.py tests/test_private_scheduler_script.py -q`; expected all PASS.
- [ ] **Step 2: Run full suite**: `pytest -q`; expected no regressions in existing public collector tests.
- [ ] **Step 3: Run static safety scan**: `rg -n "orders|withdraw|transfer|submit|cancel|write" bitfinex_lending/private_*.py scripts/install-private-account-collector.ps1`; manually verify every match is a deny-list check or documentation string, not an API call.
- [ ] **Step 4: Execute local `--dry-run` with intentionally absent credentials**; expected fail-closed exit and no authenticated request.
- [ ] **Step 5: After the user supplies local credentials outside chat, execute one real read-only collection manually, inspect four account files, then show the scheduler preview. Do not enable the task until the user explicitly asks to enable it.
- [ ] **Step 6: Record results and the 24-hour observation requirement in `progress.md` and `todo.md`.
