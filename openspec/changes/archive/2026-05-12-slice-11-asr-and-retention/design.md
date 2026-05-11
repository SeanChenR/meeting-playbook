## Context

ASR 引擎 + recording cleanup 兩件 infra 工作，合一個 slice 因為都在 detail page 上半 metadata 卡片同個區塊出現（三個新 UI 元素：selector / badge / button），且都不動 user-facing UX 太多。Slice 6（slice-06-mic-transcript-session）建立的 `ASRProvider` Protocol 是 ADR-0005 keystone，Qwen3 是第二個實作；Slice 6 同時建了 `recording` 表但沒做 retention cleanup，本 slice 補上。

**現有可重用設施**:
- `asr/base.py` — `ASRProvider` Protocol + `TranscriptChunk` dataclass（slice 6）
- `asr/whisper_provider.py` — Whisper 實作 reference（slice 6）
- `sessions/dependencies.py` — `_whisper_singleton_me/counterparty` lru_cache 模式（要替換）
- `sessions/router.py` — WS connect 時拿 providers + warmup（要更新從 meeting 拿 provider name）
- `sessions/repository.py` — `SessionRepository.list_chunks_for_meeting` + `insert_chunk`（re-run 會用到）
- `meetings/models.py` — `Meeting.asr_provider` 欄位（slice 3）已存在 default `whisper`
- `recording` 表（slice 6）— 需要加 `deleted_at` column
- `meeting_playbook/config.py::Settings` — pydantic-settings 模式（加新欄位）
- `slice-10` summary `runtime.py` 模式 — in-flight registry + `asyncio.Task` + `_lock` — re-run 直接複用同模式
- 沒 FastAPI `lifespan`（之前沒任何啟動 hook 需求） — 本 slice 加

**用戶價值**：
1. ASR 中文 transcript 品質從 WER 19.11 → 5.88（3.2× 改善），對 B2B 中文會議是決定性差距
2. 老會議錄音不再永遠堆在磁碟（30 天自動清）
3. 老 Whisper 會議想升級 → 點「重新轉錄」→ 拿到新版高品質 transcript

## Goals / Non-Goals

**Goals:**

- Qwen3 + Whisper 並存，新會議預設 Qwen3（per Sean's Q1 拍板），Whisper 仍是英文 / 多語 fallback
- Provider 選擇在 WS connect 時依 `meeting.asr_provider` 動態決定；switch 下一場才生效
- `recording` 30 天後 wav 檔自動刪 + `deleted_at` 設 timestamp，row 永留
- Re-run ASR：原子替換 transcript_chunk（單一 transaction），失敗不留 partial 狀態
- Re-run 進度透過 HTTP polling 報給前端（per Sean's Q1 拍板）
- Selector + button + badge 全在 detail 頁面 metadata 卡片（per Sean's Q2 拍板）

**Non-Goals:**

- 第三家 ASR provider — 純 Whisper + Qwen3
- 即時切換 provider — 切了下一場才生效
- WebSocket push 報 progress — 純 HTTP polling
- 不同 retention 期間 per meeting — 全域 setting
- Soft delete row recovery — `deleted_at` 單向
- ASR provider 自動偵測語言
- Re-run cancel 功能
- Re-run 跨多 meeting 批次
- Re-run 寫進新 row（保留歷史版本）— 直接覆寫
- APScheduler — 用 `asyncio.sleep(24h)` 純迴圈
- VibeVoice — ADR-0028 已 deprecate
- ASR 影響 advisor / summary prompt — provider 對下游透明

## Decisions

### Decision 1: Provider 切換 timing — WS connect 時依 meeting.asr_provider 動態選

替換既有 `sessions/dependencies.py` 的 `_whisper_singleton_me/counterparty` lru_cache 模式：

```python
# asr/factory.py
@lru_cache
def _provider_singleton(provider_name: str, stream: Stream) -> ASRProvider:
    if provider_name == "qwen3":
        return Qwen3ASRProvider(stream=stream)
    return WhisperProvider()  # whisper default fallback for any unknown name

def get_asr_providers_for_meeting(provider_name: str) -> dict[Stream, ASRProvider]:
    return {
        "me": _provider_singleton(provider_name, "me"),
        "counterparty": _provider_singleton(provider_name, "counterparty"),
    }
```

`sessions/router.py::meeting_session_endpoint` 在 WS connect 時拿到 `meeting`（path 已驗證 ownership），call `get_asr_providers_for_meeting(meeting.asr_provider)` 拿到 dict[Stream, Provider]，傳進 `SessionService`。Warmup 維持 lazy（第一次該 provider+stream 組合 transcribe 時才載 model，~10-25s 同 Whisper 體驗）。

**Rationale**: 既有 dependency injection 模式 `get_asr_providers_dependency()` 沒辦法依 meeting 切換（FastAPI dependency 在 path resolve 之前就執行）。直接在 router handler 內 call factory，meeting_id 已知，最簡單。

**Alternatives considered**:
- A: Eager warmup at app boot — 兩個 provider × 兩個 stream = 4 個 model load ≈ 8GB RAM + 60s cold start，scope creep
- B (採用): WS connect 時拿 + lazy warmup
- C: 把 provider 切換邏輯下推到 SessionService 內 — service 不該管 DI

### Decision 2: `Meeting.asr_provider` default 改 qwen3，**不 back-fill 既有 row**

```python
# meetings/models.py
asr_provider: Mapped[str] = mapped_column(Text, nullable=False, default="qwen3")  # was "whisper"
```

Alembic migration 不寫 `UPDATE meeting SET asr_provider = 'qwen3' WHERE asr_provider = 'whisper'`。原因：老 meeting 的 transcript_chunk row 是用 Whisper 跑的（`asr_provider_used = 'whisper'`），保留 `meeting.asr_provider = 'whisper'` 反映「這場是 Whisper 錄的」歷史事實。Sean 想升級的話手動 selector 切 → 按 re-run。

**Rationale**: 預設 qwen3 反映 Sean 主要 use case（中文 B2B）；不 back-fill 避免「meeting.asr_provider 跟 transcript 實際 provider 不一致」的隱性衝突。

**Alternatives considered**:
- A: Back-fill 全部既有 row 變 qwen3 → 顯示上 selector 選 Qwen3 但 transcript 實際是 Whisper 的，誤導
- B (採用): 預設 qwen3，但只影響新 meeting；既有 row 維持

### Decision 3: Re-run 採 in-flight registry + 原子 DELETE+INSERT 替換

複用 slice-10 summary `runtime.py` 模式：

```python
# rerun/runtime.py
_inflight: dict[str, asyncio.Task] = {}
_progress: dict[str, ChunksProgress] = {}  # extra: per-meeting (processed, total)
_lock = asyncio.Lock()

async def spawn_rerun_task(meeting_id: str, ...) -> bool:
    """Returns True if spawned; False if already in-flight."""
    async with _lock:
        if (existing := _inflight.get(meeting_id)) and not existing.done():
            return False
        task = asyncio.create_task(_run(meeting_id), name=f"rerun-{meeting_id}")
        _inflight[meeting_id] = task
        _progress[meeting_id] = ChunksProgress(processed=0, total=0)
    return True

def get_status(meeting_id: str) -> dict:
    task = _inflight.get(meeting_id)
    if task is None or task.done():
        return {"status": "idle", "chunks_processed": 0, "chunks_total": 0}
    p = _progress.get(meeting_id, ChunksProgress(0, 0))
    return {"status": "pending", "chunks_processed": p.processed, "chunks_total": p.total}
```

背景 task：
1. 開新 AsyncSession（同 slice-10 separate-session pattern）
2. 拿 meeting + recordings → 兩個 wav 檔路徑
3. 每個 wav → load → chunk into 10s windows → estimate `total_chunks`，更新 `_progress`
4. 對每 chunk：用 `meeting.asr_provider` 對應 provider 的 `transcribe_chunk`，蒐集到 in-memory list；progress.processed += 1
5. 全部成功 → 單一 transaction：`DELETE FROM transcript_chunk WHERE meeting_id = ?` → `INSERT ... RETURNING`（原子替換）
6. 任何 chunk inference 失敗 → log + 跳出 → 不動既有 transcript_chunk + 不寫 partial
7. `finally` block pop _inflight + _progress

**Rationale**: 失敗不留 partial 是必要的 — 一半新一半舊的 transcript 比沒 re-run 更糟。原子 SQL 替換用單一 transaction 包 DELETE + INSERT，PostgreSQL 自動處理隔離。

**Alternatives considered**:
- A: 寫進新 transcript_chunk row（保留歷史版本）+ 加 version column → 過度設計，YAGNI
- B (採用): 原子覆寫
- C: 流式 INSERT（每 chunk 一個 INSERT）→ 失敗時留 partial 違反 contract

### Decision 4: HTTP polling for re-run progress

前端用 React Query polling 每 1 秒打 GET `/api/meetings/{id}/rerun_asr_status`。Polling 啟動條件：本地 `mutationState === "pending"` OR 上次 GET 回 `{status: "pending"}`。

```typescript
const { data } = useQuery(
  rerunStatusQueryOptions(meetingId, {
    enabled: rerunMutation.isPending || isRerunPending,
    refetchInterval: (q) => q.state.data?.status === "pending" ? 1000 : false,
  })
);
```

完成偵測：`data.status === "idle"` AND 之前是 `pending` → invalidate `["transcripts", meetingId]` cache → workspace transcript pane 自動 refetch 拿到新版。

**Rationale**: Slice 10 summary 同樣 polling 模式驗證過 OK；2-5 分鐘的 task 不用即時推送，1 秒延遲可接受；不用開新 WS / 重複 lifecycle。

**Alternatives considered**:
- A: WebSocket push — 多一個 lifecycle，跟既有 session WS 混淆
- B (採用): HTTP polling
- C: 不顯示進度只 spinner — 5 分鐘 user 以為 hang

### Decision 5: `recording.deleted_at` schema + cleanup 不刪 row

```sql
ALTER TABLE recording ADD COLUMN deleted_at TIMESTAMPTZ NULL;
```

Cleanup logic：

```python
# retention/job.py
async def cleanup(now: datetime, *, retention_days: int, recordings_dir: Path) -> int:
    """Returns count of files deleted."""
    threshold = now - timedelta(days=retention_days)
    async with session_factory() as session:
        rows = await session.execute(
            select(Recording).where(
                Recording.created_at < threshold,
                Recording.deleted_at.is_(None),
            )
        )
        deleted_count = 0
        for rec in rows.scalars():
            wav_path = Path(rec.file_path)
            try:
                if wav_path.exists():
                    wav_path.unlink()
                rec.deleted_at = now
                deleted_count += 1
            except OSError as exc:
                logger.warning("retention skip %s: %s", wav_path, exc)
        await session.commit()
        return deleted_count
```

`deleted_at IS NULL` = 唯一「錄音可用」predicate。不檢查磁碟（DB 是 source of truth；也涵蓋手動 `rm` 的 case）。

**Rationale**: Issue #14 明確要求保留 row。`deleted_at IS NULL` 比 disk check 便宜（一個 SQL）也更可靠。

**Alternatives considered**:
- A: 硬刪 row → 失去歷史
- B (採用): soft delete via timestamp
- C: 加另一個 `is_deleted` boolean → 多冗欄位（boolean 可從 timestamp 推）

### Decision 6: Cleanup job 用簡單 `asyncio.sleep(24h)` 迴圈 + FastAPI lifespan

```python
# retention/runtime.py
async def run_forever(*, settings: Settings) -> None:
    """Background loop: cleanup once at startup, then every 24h."""
    while True:
        try:
            count = await job.cleanup(
                now=datetime.now(UTC),
                retention_days=settings.recording_retention_days,
                recordings_dir=Path(settings.recordings_dir).expanduser(),
            )
            logger.info("retention sweep: deleted %d wav files", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("retention sweep failed; will retry next cycle")
        await asyncio.sleep(24 * 3600)

# server.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task = asyncio.create_task(retention.runtime.run_forever(settings=settings))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

app = FastAPI(lifespan=lifespan, ...)
```

第一次 sweep 在啟動時跑（即時清乾淨）；之後每 24h 一次。失敗只 log，下次還會跑。

**Rationale**: APScheduler 對單一 daily job 過設計（多依賴 + scheduler state）。`asyncio.sleep` 純 stdlib 夠用。

**Alternatives considered**:
- A: APScheduler — 多依賴
- B (採用): asyncio.sleep loop
- C: 系統 cron + 內部 endpoint trigger — 多了 ops 配置 + 跨 single-machine 不對稱

### Decision 7: UI 三件 + Recording badge 用色彩 dot 不用 emoji

Detail 頁面 metadata 卡片（既有「對方 / 我方 / 狀態 / ASR 引擎 / 建立時間」list）改造：
- 既有「ASR 引擎」label 換成 `<AsrProviderSelector>` dropdown（Whisper / Qwen3）
- 「狀態」label 下方新加一行「錄音」+ `<RecordingBadge>` — `<span className="bg-green-500 dot" />` + 文字「錄音可用」/「錄音已過期」
- 「建立時間」之後新加「重新轉錄」action row，含 `<RerunButton>`（gating：completed + recordings_available + 非 pending）

按 Sean memory `feedback_ui_standards_no_emoji_magicui` — 不加 emoji，用 Tailwind 色 dot + 純文字。

```
┌─ Q3 review ─────────────────────────┐
│ 對方        林經理                    │
│ 我方        Sean                      │
│ 狀態        已結束                    │
│ 錄音        🟢 錄音可用                │ ← (色 dot 無 emoji)
│ ASR 引擎    [Qwen3 ▾]                 │ ← (selector)
│ 建立時間    5/11 02:30                │
│ ─────────────────────────────────── │
│ [重新轉錄] (visible only when ...)    │
└──────────────────────────────────────┘
```

Re-run 按下後 → workspace tab 的 transcript pane 立刻 overlay：

```
┌─ 即時逐字稿 ────────────────────────┐
│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒              │ ← skeleton
│                                       │
│ 重新轉錄中... (12/45 chunks)          │ ← polling-driven progress
└──────────────────────────────────────┘
```

完成後 invalidate `["transcripts", meetingId]` → React Query 自動重抓 → transcript 切回正常顯示模式 + 新內容。

### Decision 8: MLX dep 選擇 — apply 階段 spike 確認

`doggy8088/Qwen3-ASR-1.7B-MLX-8bit` 的 model card 沒明寫用哪個 MLX loader package。兩個候選：
- `mlx-lm` — generic MLX language model loader（chat / completion）
- `mlx-whisper` — MLX-optimized whisper loader（已假設 ASR-flavored API）

Apply 階段第一個 task 先 5-10 分鐘 spike：本地 download model → 嘗試 load → 確認 `transcribe(audio_path) -> str` 或類似 API → 寫進 `Qwen3ASRProvider.transcribe_chunk`。如果兩個都不對就用 `transformers + mlx` 直接調 — 最後 fallback。

**Rationale**: 不在 propose 階段卡這個（model loader API 是 implementation detail，Protocol 不變）。spike 半小時內可確認，apply 內部處理。

**Alternatives considered**:
- A: Propose 階段先 spike → 卡住 propose
- B (採用): Apply 階段第一個 task spike → minimum risk，最壞情況改 import 一行
- C: 不依 MLX，純 transformers + MPS → 慢 3-4×，model 大 4×（用 fp16 而非 8-bit）

### Decision 9: Re-run 進行中時 summary trigger / regenerate 行為

不阻擋。Re-run 完成 → invalidate transcript cache → 下次 user 看 summary tab → React Query 對 summary 也 invalidate？— 不，summary 邏輯不變。Summary stale 偵測（slice 10 既有）會看 `transcript.created_at > summary.generated_at`，新 chunk 的 created_at 是現在 → summary 自動 stale → user 看到「⚠ 內容已更新，建議重新生成」alert → 自己決定要不要 regenerate。

**Rationale**: 不需要為 re-run 特殊處理 summary — 既有 stale 機制就涵蓋。

**Alternatives considered**:
- A: Re-run 自動觸發 summary regenerate → 越權；user 可能不想花 token
- B (採用): 靠既有 stale alert 提示
- C: Re-run 期間 disable summary regenerate button → 過度防禦

## Implementation Contract

### Behavior contract

1. **ASR Provider 切換**：新會議 `Meeting.asr_provider` 預設 `qwen3`。User 在 detail 頁面 metadata 卡片 dropdown 切到 Whisper → PUT `/api/meetings/{id}` → 寫 `meeting.asr_provider`。下次 WS connect 時 `get_asr_providers_for_meeting(meeting.asr_provider)` 拿到對應 provider；warmup lazy。
2. **Recording cleanup**：FastAPI 啟動時 spawn `retention.runtime.run_forever`；第一次 sweep 立即跑；之後每 24h 一次。`cleanup(now)` 找 `created_at < now() - retention_days AND deleted_at IS NULL` 的 row → 對每個 wav 檔 `unlink()` + 設 `deleted_at = now()` → commit。
3. **Re-run ASR endpoint**：`POST /api/meetings/{id}/rerun_asr` → 驗證 ownership / status=completed / recordings_available → 透過 `rerun.runtime.spawn_rerun_task` spawn 背景 task → 202 `{status: "pending"}`。Busy 時 409 `rerun.busy`；recordings 過期 410 `rerun.recording_expired`；非 owner / 不存在 404 `meeting.not_found`；status 非 completed 422 `rerun.not_completed`。
4. **Re-run background task**：開新 AsyncSession → 拿 meeting + 兩個 recording rows → 對每個 wav: load → chunk 成 10s windows → estimate total → 用 `meeting.asr_provider` provider transcribe each chunk → 蒐集到 list（記憶體）→ 全部成功後單一 transaction：`DELETE FROM transcript_chunk WHERE meeting_id = ?` + `INSERT ... RETURNING` → commit → 更新 `_progress` → pop `_inflight`。失敗：log + 跳出 + 不動既有 row。
5. **Re-run progress polling**：`GET /api/meetings/{id}/rerun_asr_status` → `{status: "idle"|"pending"|"failed", chunks_processed: int, chunks_total: int}`。前端 React Query 1s polling 直到 `status !== "pending"`。完成 → invalidate `["transcripts", meetingId]` cache。
6. **`recording_available` 判定**：GET `/api/meetings/{id}` 加 `recordings_available: bool` 欄位，true iff 該 meeting 有至少一個 recording 且 `deleted_at IS NULL`。沒任何 recording 時 false。
7. **UI gating**：Re-run button 出現條件 = `meeting.status === "completed" AND meeting.recordings_available === true AND meeting.rerun_asr_pending === false`。三個都 true 才 render。
8. **Re-run pending overlay**：transcript pane 在 `rerun_asr_pending === true` OR `useRerunStatus().status === "pending"` 時 render skeleton + 「重新轉錄中... ({n}/{總} chunks)」。

### Data shapes

**Meeting GET response 新增欄位**:
```typescript
type Meeting = {
  // ... 既有欄位
  recordings_available: boolean;   // false 當所有 recording 的 deleted_at IS NOT NULL，或無任何 recording
  rerun_asr_pending: boolean;      // true 當 rerun_runtime._inflight 有 unfinished task
};
```

**Recording schema 加欄位**:
```sql
recording.deleted_at TIMESTAMPTZ NULL  -- NULL = 仍可用；NOT NULL = wav 已被 cleanup 刪
```

**Re-run status response**:
```typescript
type RerunStatus = {
  status: "idle" | "pending" | "failed";  // failed = 上次 task raised exception，下次 POST 重設
  chunks_processed: number;
  chunks_total: number;  // 0 if status === "idle"
};
```

### Failure modes

- **Qwen3 model download 失敗**（首次）→ propagate exception；user 看到 WS error frame `session.stream_failed_at_start`；要重連
- **Qwen3 inference exception per chunk**（Re-run 過程）→ log + 跳出 task + 不動既有 transcript_chunk + 不寫 partial → user 下次 GET status 看到 `failed` → 可重試
- **Re-run wav 檔不在磁碟**（`deleted_at IS NULL` 但 `unlink` race，譬如 retention 同時跑）→ FileNotFoundError → log warning + 設 `deleted_at = now()` 補正資料 + raise SummaryRecordingMissing → user 看到 `failed`
- **Cleanup `unlink` 失敗**（permission / FS error）→ log warning + skip 該 row（不設 deleted_at）+ 下次 sweep 重試
- **Cleanup DB UPDATE 失敗** → 整個 transaction rollback；wav 檔已實體刪但 DB 未更新 → 下次 sweep 看到 row 還在 + 試 unlink → FileNotFoundError → log + 設 deleted_at（自我修復）
- **同 meeting 同時 spawn rerun + summary regenerate** → 兩條 task 各自 separate AsyncSession，不衝突；但 summary 會看到 stale transcript（rerun 還沒完成 commit）→ summary 用舊 transcript 生成 → 結束後既有 stale 機制標 summary stale → user 看 alert
- **lifespan 異常**（retention task 創建失敗）→ FastAPI 啟動失敗 → 整個 backend down → 維運人員注意 log

### Acceptance criteria

- 後端 `pytest packages/backend` 全綠（含新 asr / retention / rerun 整套測試）
- 前端 `bun test packages/web` 無新失敗（既有 8 baseline 失敗保留）
- locale parity guard 過
- Manual smoke-test (Sean): apply migration → 啟動 dev stack → 開新會議 → metadata 卡片 selector 預設「Qwen3」→ 講中文幾句 → end → 看到 transcript 中文比 Whisper 順 → 切 selector 到 Whisper → 沒立即生效（hint 顯示）→ 開下一場 → 確實是 Whisper → 再開老會議（用 Whisper 錄的）→ 切 selector 到 Qwen3 → 按「重新轉錄」→ skeleton + 進度 → 完成 → workspace transcript 是 Qwen3 版本 → 改 `RECORDING_RETENTION_DAYS=0` 重啟 → cleanup 立即跑 → 看到 wav 檔被刪 + DB row 的 `deleted_at` 有值 + UI badge 變「錄音已過期」+ Re-run 按鈕消失

### Scope boundaries (in / out)

**In scope**:
- `Qwen3ASRProvider` 實作 + Hugging Face download 流程
- `asr/factory.py` 替換既有 lru_cache singletons
- `Meeting.asr_provider` default 改 qwen3
- WS connect 時 dynamic provider selection
- `recording.deleted_at` migration + cleanup job + lifespan integration
- `RECORDING_RETENTION_DAYS` config + `.env.example`
- POST /rerun_asr + GET status endpoints
- Re-run runtime registry + 原子 transcript 替換
- `recordings_available` + `rerun_asr_pending` 加進 GET meeting response
- 前端：AsrProviderSelector / RecordingBadge / RerunButton + use-rerun-status hook
- TranscriptPane re-run pending overlay
- detail.tsx metadata 卡片整合
- i18n keys

**Out of scope**:
- 第三家 ASR provider
- 即時 provider 切換（開會議中換）
- WS push for progress
- Per-meeting retention 期間
- Soft delete recovery / undelete
- ASR 自動語言偵測
- Re-run cancel
- Re-run 跨多場 batch
- 轉錄版本控（保留歷史）
- APScheduler
- VibeVoice 任何殘餘
- Meeting delete 同步刪 wav（既有 known limitation）
- 既有 wav 檔磁碟狀態 backfill
- ASR 影響 advisor / summary prompt

## Risks / Trade-offs

- **Qwen3 model 首次 download 慢（~2.5GB）** → 會議第一次連 WS 卡住數分鐘。Mitigation: download 走 HuggingFace Hub cache，第二次以後即時；docs/agents/asr-providers.md 文檔提示首次設置時間
- **Qwen3 對英文表現未測** → ADR-0028 沒英文 benchmark；Sean 偶爾英文會議要手動切 Whisper。Mitigation: selector + hover hint 「英文會議建議切 Whisper」；docs 記錄
- **MLX 8-bit + 兩個 stream = 5GB RAM** → M3 Pro 18GB 安全範圍，但若同時 advisor + summary 跑 → 加 Vertex SDK 記憶體 → 接近極限。Mitigation: ADR-0028 已分析過記憶體預算；side project 單機跑無 production 級壓力
- **Re-run inference 慢** → 5 分鐘 audio × ~5s 推論 / chunk × 60 chunks ≈ 5 分鐘 wall-clock 等待。Mitigation: progress 顯示給 user 安心；不阻擋其他 UI 操作（user 可切 tab、滑 transcript history）
- **Re-run 成功後 summary 仍 stale** → user 要再點 regenerate 才更新 summary。Mitigation: stale alert 既有；user 自決
- **Cleanup race**（user 開 detail 頁面當下 retention sweep 跑）→ user 看到「錄音可用」但下個動作 re-run 拿到 410 expired。Mitigation: rare race；UI re-fetch 後自然修正；不刻意阻擋
- **Lifespan startup 卡住** → retention task spawn 失敗會 propagate → FastAPI 起不來 → 整個 backend down。Mitigation: spawn 用 `with contextlib.suppress(Exception)` 包；最壞 retention 不跑但 backend 還能起
- **預設改 qwen3 = 老 Whisper user 困惑** → 既有 meeting 顯示 Whisper（per Decision 2 不 backfill），但新建 meeting 變 Qwen3，第一個新 meeting 的 cold start 慢 ~25s。Mitigation: docs 提示

## Migration Plan

1. Alembic migration `0007_add_recording_deleted_at`：加欄位（無 default 改動，純加新 NULL column）；`alembic upgrade head` 跑過。
2. Alembic migration **不**改 meeting 表 default — `models.py` 改 default 只影響新插入 row（既有 row 不動）。
3. Backend deploy：新 retention / rerun / qwen3 module + sessions/router.py 更新到 use factory（既有 dual-stream WS 流程不變）。
4. **首次啟動** Qwen3 download 模型 ~2.5GB；提示用戶 docs/agents/asr-providers.md。
5. Frontend deploy：detail 頁面 metadata 卡片三個新元件；舊 user 看到的 ASR 引擎欄位變 selector，預設值仍是該 meeting 的歷史 provider。
6. 文件：`docs/agents/asr-providers.md`（更新）+ `docs/agents/recording-retention.md`（新增）。

無 down-migration 必要；rollback 走 `git revert` + `alembic downgrade -1`，DB 多一個 NULL column 不影響其他功能。
