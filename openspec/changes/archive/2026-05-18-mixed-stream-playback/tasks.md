## 1. Backend：mixer module (TDD red → green)

> 涵蓋 spec requirement「mix_pcm_int16 averages two equal-length int16 PCM byte buffers without overflow」與
> 「ensure_mixed_wav is lazy, idempotent, and zero-pads the shorter stream」（audio-playback）。
> 對應 design 決策「D2. Mix algorithm：sample-by-sample 平均，shorter side zero-pad」+「D3. Lazy compute on first range request」。

- [x] 1.1 新檔 `packages/backend/tests/audio_playback/test_mixer.py`：
      先寫四個 `mix_pcm_int16` test case（spec scenarios 對應）：
      `test_mix_two_silent_buffers_returns_silence` — 4000 int16 zero × 兩邊 → 4000 int16 zero；
      `test_mix_plus_minus_constants_yields_zero` — 100 個 +1000 × 100 個 -1000 → 100 個 0；
      `test_mix_max_amplitudes_does_not_overflow` — 100 個 +32767 × 2 邊 → 100 個 +32767（不可變負）；
      `test_mismatched_length_raises_value_error` — `len(left) != len(right)` 拋 `ValueError`。
      跑 → 預期 RED（module 不存在 → ImportError）。

- [x] 1.2 新檔 `packages/backend/meeting_playbook/audio_playback/mixer.py` 實作 `mix_pcm_int16`：
      `np.frombuffer(...).astype(np.int32)` + `((L + R) // 2).astype(np.int16).tobytes()`；
      `if len(left) != len(right): raise ValueError(...)`。
      跑 1.1 的 test → 預期 GREEN 全綠。

- [x] 1.3 擴 `tests/audio_playback/test_mixer.py` 加 `ensure_mixed_wav` 三個 test case：
      `test_ensure_mix_first_call_writes_then_second_call_returns_cached_path` — mock `me.wav` + `counterparty.wav` on tmp_path → 第一次 call 後 `mixed.wav` 存在；第二次 call 後 `st_mtime` 相同（沒重寫）；
      `test_ensure_mix_missing_me_raises_mixer_input_missing` — 只 `counterparty.wav` → 拋 `MixerInputMissing`；
      `test_ensure_mix_shorter_side_zero_padded` — me = 1000 samples @ +5000, counterparty = 500 samples @ +3000 → mixed 長度 1000 samples，前 500 都 4000、後 500 都 2500。
      跑 → 預期 RED（`ensure_mixed_wav` 還沒實作）。

- [x] 1.4 `packages/backend/meeting_playbook/audio_playback/mixer.py` 加 `ensure_mixed_wav(meeting_id, recordings_dir)`：
      - 定義 exception classes `MixerError`（base）+ `MixerInputMissing(MixerError)`
      - 若 `mixed.wav` 存在直接 return Path
      - 若 `me.wav` 或 `counterparty.wav` 任一 missing 拋 `MixerInputMissing`
      - 用 `wave` 模組讀兩邊 PCM data section、`max(len)` 算 padding、`bytes(n).ljust(target_len, b'\x00')` zero-pad（int16 silence = `0x0000` byte 是 `\x00`）
      - call `mix_pcm_int16(me_padded, counterparty_padded)`
      - 寫 `mixed.wav.tmp`（用 `wave.open` mono 16 kHz 16-bit）→ `os.rename` atomic → `mixed.wav`
      - return path
      跑 1.3 的 test → 預期 GREEN。

## 2. Backend：mixed-stream endpoint (TDD red → green)

> 涵蓋 spec requirement「GET /api/meetings/{id}/recordings/mixed/audio serves the dual-stream mix as a Range-aware mono stream」（audio-playback）。
> 對應 design 決策「D1. Server-side mix」+「D4. URL pattern」+「D9. Mix failure handling」。

- [x] 2.1 新檔 `packages/backend/tests/audio_playback/test_router_mixed.py`：
      四個 test case（spec scenarios 對應）：
      `test_first_request_triggers_mix_then_serves_range` — seed dual-channel meeting + me/counterparty wav on tmp → GET 帶 `Range: bytes=0-1048575` → assert 206 + `Content-Range` header + `mixed.wav` 在 disk；
      `test_second_request_reads_cached_mix` — pre-seed `mixed.wav` + stamp `st_mtime` → GET → assert response 內容 + `mixed.wav` `st_mtime` 跟 stamp 相同（沒重寫）；
      `test_single_channel_meeting_returns_404_mixed_not_applicable` — 只 seed `me.wav` → GET → assert 404 + `error_code: recording.mixed_not_applicable`；
      `test_corrupt_counterparty_wav_returns_500_mix_failed` — `counterparty.wav` 寫亂 byte 觸發 wave.Error → GET → assert 500 + `error_code: recording.mix_failed` + 沒留 `mixed.wav.tmp`。
      跑 → 預期 RED（endpoint 不存在）。

- [x] 2.2 `packages/backend/meeting_playbook/audio_playback/router.py` 加新 handler：
      `@router.get("/api/meetings/{meeting_id}/recordings/mixed/audio")` 接 `start` / `end` / Range header（共用既有 `compute_byte_range` + `parse_range_header`）。
      - call `ensure_mixed_wav(meeting_id, recordings_dir)` 進 try/except 包：
        - `MixerInputMissing` → raise `HTTPException(404, detail={"error_code": "recording.mixed_not_applicable", "message": ...})`
        - `MixerError | wave.Error | OSError | ValueError` → cleanup any `mixed.wav.tmp` if exists → raise `HTTPException(500, detail={"error_code": "recording.mix_failed", ...})`
      - 之後跟既有 per-recording handler 邏輯一樣（StreamingResponse + Range + cap）
      - Ownership check 共用既有 dependency
      跑 2.1 test → 預期 GREEN。

## 3. Frontend：API helper + pickMeetingRecording 升級

> 涵蓋 spec MODIFIED requirement「MeetingAudioMiniPlayer is a sticky bottom control bar」的「dual-channel `pickMeetingRecording` 回 `kind: dual` + `sources.mixed`」部分。

- [x] 3.1 `packages/web/src/lib/meetings-api.ts`：
      新增 `mixedAudioUrl(meetingId: string, params?: { start?: number; end?: number }) -> string`：
      回 `/api/meetings/{encodeURIComponent(meetingId)}/recordings/mixed/audio` + 可選 `?start=&end=` query。
      既有 `recordingAudioUrl` 函式不動。
      **驗證**：擴 `packages/web/src/lib/meetings-api.test.ts` 加兩個 case —
      `mixedAudioUrl_returns_base_url_without_query_when_no_params`、
      `mixedAudioUrl_encodes_meeting_id_and_includes_start_end`。

- [x] 3.2 `packages/web/src/hooks/use-mini-player.ts`（或 `pickMeetingRecording` 所在 module）：
      `pickMeetingRecording(recordings)` return shape 升級為 `{ kind: "dual" | "single" | "none", sources: { mixed?: string; me?: string; counterparty?: string }, defaultSource: "mixed" | "me" }` —
      - 兩個 stream 都在 → `kind: "dual"`, `sources: { mixed: mixedAudioUrl(id), me: recordingAudioUrl(id, meRow.id), counterparty: recordingAudioUrl(id, cpRow.id) }`, `defaultSource: "mixed"`
      - 只一個 stream → `kind: "single"`, `sources: { me: recordingAudioUrl(id, recRow.id) }`, `defaultSource: "me"`
      - 沒任何 recording → `kind: "none"`, `sources: {}`, `defaultSource: "me"`（不會被讀）
      **驗證**：擴 `packages/web/src/hooks/use-mini-player.test.ts`（既有 `pickMeetingRecording` test 改寫成新 shape）+ 新加 case
      `pickMeetingRecording_dual_returns_mixed_default_with_three_sources`、
      `pickMeetingRecording_single_returns_me_only_no_mixed`、
      `pickMeetingRecording_no_recordings_returns_kind_none`。

## 4. Frontend：mini-player source toggle UI

> 涵蓋 spec requirement「MeetingAudioMiniPlayer source toggle switches between mixed / me / counterparty while preserving currentTime」+ MODIFIED requirement 的「toggle UI + error inline」段（audio-playback）。
> 對應 design 決策「D5. Toggle UI」+「D6. localStorage」+「D9. Mix failure 不靜默 fallback」。

- [x] 4.1 `packages/web/src/components/meeting-audio-mini-player.tsx`：
      新加 `currentSource` state（type `"mixed" | "me" | "counterparty"`），初始值從 `localStorage.miniPlayerSource` 讀（無效 / 不存在 fallback `"mixed"`）；
      改 `audioSrc` 計算：依 `currentSource` 從 `pickMeetingRecording` 結果的 `sources` 挑對應 URL；
      `kind === "dual"` 時加 render `<SourceToggle>` segment（`data-testid="mini-player-source-toggle"`），三個 button `data-testid="source-mixed"` / `source-me"` / `source-counterparty`，active 樣式用既有 `buttonVariants({variant: "default" if active else "outline"})`；
      `kind === "single"` 或 `"none"` 時 toggle 不 render；
      `handleSourceChange(next)`：算當前 `audio.currentTime` + `paused` → setCurrentSource(next) + setItem localStorage → useEffect 監測 `audioSrc` 變化 → 在 `onLoadedMetadata` 內 set `currentTime` 回原值、若原 playing 則 `play()`。
      **驗證**：擴 `packages/web/src/components/meeting-audio-mini-player.test.tsx` 三 case —
      `dual_channel_toggle_renders_three_buttons_with_mixed_active`、
      `single_channel_toggle_does_not_render`、
      `toggle_to_counterparty_preserves_currentTime_and_paused_state`（mock audio element + fireEvent click → assert localStorage + src + currentTime restore）。

- [x] 4.2 同檔加 mix-failure inline error：
      `<audio>` `onError` handler：若 `currentSource === "mixed"` 且 error code = `recording.mix_failed` 或 `recording.mixed_not_applicable`（從 audio element 的 error event 拿到 — 實際上 `<audio>` 的 onError 不直接給 backend code，所以需要 fetch `audioSrc` 一次驗證、422/500 時 setErrorMessage + 不切換 source）；
      改用 `useQuery` pre-fetch HEAD 或不做 pre-fetch、依賴 `<audio>` `onError`、再用 fetch backup 拿 error envelope。
      最小實作：用 `fetch(audioSrc, { method: "HEAD" })` 在 `currentSource` change 時跑一次驗證（200 / 206 OK 才繼續、否則 setErrorMessage `localizedErrorMessage(error_code, t)` 從 HEAD response 拿不到 body，所以用 `GET ?probe=1`，但 backend 沒這 query — 改：用 `fetch(audioSrc, { headers: { Range: "bytes=0-0" } })` 拿 1 byte，response.ok = true 繼續、!ok 讀 body json 拿 `error_code`）；
      切回邏輯：error 時不自動切回 me-only，仍保 `currentSource = "mixed"` 高亮，user 點 toggle 手動切。
      **驗證**：同檔再加 test
      `mixed_endpoint_500_renders_inline_alert_and_keeps_source_mixed`（mock fetch HEAD 回 500 + body `{error_code:"recording.mix_failed"}` → assert `<Alert>` render + source button mixed 仍 active + 沒 setItem localStorage 切到 me）。

## 5. Frontend：i18n keys

> i18n parity test 會擋住單邊新增 key 漏 sync。

- [x] 5.1 兩份 locale 同步新增 5 個 keys（dual-channel toggle labels + error codes）:
      `meeting.detail.audioPlayer.source.mixed` — zh-TW: `"混音"`；en: `"Mixed"`
      `meeting.detail.audioPlayer.source.me` — zh-TW: `"我方"`；en: `"Me"`
      `meeting.detail.audioPlayer.source.counterparty` — zh-TW: `"對方"`；en: `"Counterparty"`
      `errors.recording.mixed_not_applicable` — zh-TW: `"這場會議不是雙聲道錄音，無法播放混音"`；
        en: `"This meeting is not dual-channel; mixed audio is unavailable"`
      `errors.recording.mix_failed` — zh-TW: `"混音生成失敗，請改聽我方或對方單一聲道"`；
        en: `"Failed to mix audio streams; switch to the Me or Counterparty source"`
      **驗證**：跑 `bun --filter @meeting-playbook/web test src/locales/locales.test.ts` 綠燈。

## 6. 端到端驗證

- [x] 6.1 跑 full backend + web test：
      `psql postgresql://localhost:5432/meeting_playbook_test -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"` →
      backend `pytest` → web `bun test`。
      **驗證**：backend pass count 比 main 多至少 11 個（mixer 4 + ensure_mix 3 + router_mixed 4）；
      web pass count 比 main 多至少 11 個（meetings-api 2 + use-mini-player 3 + mini-player 4 + ...）；0 fail。

- [x] 6.2 手動 E2E：
      A) 開既有 dual-channel meeting detail（有錄音的） → mini-player 顯示「混音 / 我方 / 對方」三個 button、預設「混音」高亮、按 play → 第一次 loading ~1-2 秒（first mix）→ 聽到完整對話（兩邊都有聲）。
      B) 第二次同 meeting open detail / refresh → 按 play 立刻播（讀 cached `mixed.wav`、無 latency）。
      C) 切到「我方」→ src 換到 me.wav endpoint、`currentTime` 保留、繼續播只有我方聲音。
      D) 切到「對方」→ 同樣行為、只聽到對方。
      E) 切回「混音」→ 持久化生效：reload page → mini-player 還是停在最後選的 source（如果切到對方就 reload 後仍對方）。
      F) Single-channel meeting（如果有 — slice-12 single-channel UI entry 還沒做、得用 manually 把 `counterparty.wav` 刪掉模擬）：mini-player 不顯示 toggle、正常播 me。
      G) 模擬 mix 失敗（手動把 `counterparty.wav` 改成 random bytes 觸發 wave.Error）→ open detail → `<Alert>` 顯示 localized「混音生成失敗⋯」、source toggle 仍顯示、按 me / counterparty 可切過去聽。
      **驗證**：本 task 是手動 checklist；PR 描述記錄 A-G 都過。
