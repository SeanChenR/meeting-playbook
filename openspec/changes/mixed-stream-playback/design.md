## Context

Slice-06 ~ 07 落地 dual-stream capture：BlackHole（system audio = 對方）跟 microphone（我方）各自寫一個 **mono** WAV 檔到 `{RECORDINGS_DIR}/{meeting_id}/{counterparty|me}.wav`，每個檔對應 `recording` table 一個 row（`stream` column = `me` / `counterparty` / `mixed` — 後者目前沒被任何 path 寫進去）。

當下 `audio-playback` capability：
- `parse_wav_header` 只接受 mono 16 kHz 16-bit（stereo / 非 16 kHz 直接拒）
- `compute_byte_range` 算 PCM 區段是 mono 假設
- `GET /api/meetings/{id}/recordings/{recording_id}/audio` per-recording range-aware stream
- `<MeetingAudioMiniPlayer>` 用 `pickMeetingRecording(recordings)` 挑播放對象，當前邏輯：dual-channel → 挑 `stream === "me"`、single-channel → 唯一一筆

Sean 在 slice-24 收尾後實際打開 meeting detail 才發現對方那邊**整段沒聲音** —— 不是 stereo 分流到 L/R，是 player 從來沒 mount counterparty.wav。

本 slice 把這個 user-facing gap 補起來，且**動既有 audio-playback capability 而不開新 capability**（mix 還是 audio-playback 的子能力）。

## Goals / Non-Goals

**Goals**
- Dual-channel meeting 在 detail 頁按播放，預設聽到「**我方 + 對方混音的完整對話**」（單耳 / 單聲道喇叭都能聽全部）
- 不換到任何 stereo 機制（避免「左耳對方、右耳我方」的單耳失聲 UX）
- 提供 toggle 讓 user 切回單一 stream（debug / 要聽單側的場景）—— 預設 mixed
- Single-channel meeting 行為一字不變（toggle 不顯示、mixed endpoint 404）

**Non-Goals**
- client-side mix（Web Audio API 同步太複雜）
- 個別 stream 音量平衡 / ducking
- 改 `parse_wav_header` 接受 stereo
- 改 retention sweep
- 改 chunk slicing 語意（chunk timeline 跟 me/counterparty/mixed 都同長）
- 在 finalize 階段 pre-compute mixed.wav（保持 lazy on-demand）

## Decisions

### D1. Server-side mix，不做 client-side

選擇：mix 在 backend 完成，回 mono PCM；frontend 切 toggle 等於切 URL，`<audio>` 仍只有一個 element。

**理由**
- Client-side mix 需要 `<audio>` × 2 + Web Audio API graph + scrubbing 兩端 currentTime 同步 + 雙端 buffer 預載 —— 一個 single-user 個人專案不值這個複雜度
- Server-side mix 一次 read / write，cache 一份 wav，之後 range 都是純 file slice，跟既有 per-recording endpoint 同 code path

**Trade-off**：mix 失敗（disk 滿 / wav 壞）整個 mixed 都不能播；但 me / counterparty 個別 stream 仍能透過 toggle 切過去聽。

### D2. Mix algorithm：sample-by-sample 平均，shorter side zero-pad

選擇：
```
def mix_pcm_int16(left, right) -> bytes:
    # Both inputs are equal-length int16 PCM byte buffers
    L = np.frombuffer(left, dtype=np.int16).astype(np.int32)
    R = np.frombuffer(right, dtype=np.int16).astype(np.int32)
    mixed = ((L + R) // 2).astype(np.int16)  # no overflow risk
    return mixed.tobytes()
```
長度不一致時：`ensure_mixed_wav` 把短的那邊用 silence (int16 `0x0000`) zero-pad 到 `max(len(me), len(counterparty))`，再 mix。Total length = max。

**理由**
- 算術平均最直覺，使用者預期「兩個人說話聲音差不多大」
- 兩個 int16 加 = int17 範圍、shift right 1 bit 回 int16 —— **無溢位**，不需 clamp（但設計仍保留 clamp 描述以防未來 maintainer 改 alg）
- Zero-pad 短的一邊 = stream 開始 / 結束時段的單側錄音原音保留（e.g. 開頭 me 還沒講話、counterparty 已經開始）
- 用 numpy 因為 backend 已經 import numpy（whisper 用），無新依賴

**Alternative considered**：
- RMS-based normalization（兩邊 RMS 拉齊再加）：對方音量過小場景有幫助，但 metering 複雜、留給未來 slice
- 兩端 weighting：需要 UI 暴露 slider，scope 太大

### D3. Lazy compute on first range request，不 pre-compute 在 finalize

選擇：`/api/meetings/{id}/recordings/mixed/audio` handler 在每個 request 開頭 call `ensure_mixed_wav(meeting_id)`：
- 如果 `mixed.wav` 已存在 → 直接 return path
- 不存在 → mix → 寫 `mixed.wav.tmp` → atomic rename `→ mixed.wav` → return

**理由**
- 不動 sessions/router.py finalize 邏輯 —— 那 module 已經被 S20a/b/c + S24 改過很多次，scope 控小
- Mix 一個 60-min meeting（115 MB me + 115 MB counterparty）在 SSD + numpy 大概 ~1-2 秒；first range request 多等 1-2 秒可接受
- 之後所有 range request 直接 file slice，跟既有 per-recording endpoint 同性能
- Idempotent：concurrent first requests 可能各自跑 mix，但都寫 `tmp` 再 atomic rename，最後一個贏，無 corrupt 風險

**Trade-off**：第一個按播放的 user 等 1-2 秒；可接受（單人 app、第一次播放是 deliberate action）。

### D4. URL pattern：`/api/meetings/{id}/recordings/mixed/audio`

選擇：`mixed` 當作 path segment，跟 `{recording_id}` 同層；mini-player toggle 切到 me/counterparty 時 fallback 到既有 `/recordings/{recording_id}/audio`。

**理由**
- `mixed` 是固定 keyword，跟 UUID 不會撞（UUID 不會是「mixed」這字）
- 既有 endpoint 完全不動，純 add
- URL 看就懂語意 vs `?stream=mixed` query 那種 grep 比較難

**Alternative considered**：`?stream=mixed` query param on existing endpoint —— 否決，handler 邏輯要分支太多（recording_id 有 / 無）。

### D5. Toggle UI：三選一 segmented control，切換保留 `currentTime`

選擇：mini-player 加 `<SourceToggle>` segment：`混音 / 我方 / 對方` (zh-TW) / `Mixed / Me / Counterparty` (en) 三個 button；user 點切換時：
- 算當前 `audio.currentTime` 跟 `paused` state
- 改 `<audio>` `src` 到新 source 對應 URL（保留當前 chunk slice `?start=&end=`）
- `onLoadedMetadata` 後 set `currentTime` 回原值、若原本 playing 就 play

**理由**
- segmented control 對「三選一獨佔」最直覺（vs dropdown / radio）
- 切換不打斷使用者收聽位置 —— 切到對方那條繼續從同位置聽
- 跟既有 speed dropdown 行為一致（speed 切換不 reload src、source 切換 reload src 但保 currentTime）

**Trade-off**：source 切換有短暫 buffering（reload src）—— vs speed 切換零 latency。User 預期切 source 比切 speed 重，可接受。

### D6. `localStorage.miniPlayerSource` 持久化，default `mixed`

選擇：跟既有 `miniPlayerRate` 同機制；key = `miniPlayerSource`、values = `"mixed" | "me" | "counterparty"`、default = `"mixed"`。

**理由**
- Power user (debug、想聽單側) 切了之後不用每次重切
- 跨 meeting 持久化 —— 一致 mental model

### D7. Single-channel meeting：mixed endpoint 回 404，toggle 隱藏

選擇：
- Backend：`ensure_mixed_wav` 偵測 `me.wav` 或 `counterparty.wav` 任一不存在 → raise → handler 回 `404 {error_code: "recording.mixed_not_applicable", message: ...}`
- Frontend：`pickMeetingRecording` 對 single-recording meeting return 「me-only style」 結果，mini-player 看到只一個 source option 就**整個 toggle UI 不 render**

**理由**
- Single-channel 只有一個 stream、mix 沒意義
- UI 不顯示 disabled toggle 比顯示「灰掉但點不到」乾淨

### D8. Cached `mixed.wav` 跟 me/counterparty 同 retention window

選擇：不對 `mixed.wav` 加獨立 TTL；既有 retention sweep 30 天到期時 sweep 整個 `{recording_dir}/{meeting_id}/` 目錄，三個 wav 一起走。

**理由**
- 跟既有 retention 邏輯一致（per-meeting directory）
- Mixed wav 是 me + counterparty 的 derivative，me / counterparty 沒了 mixed 也不需要

### D9. Mix failure handling：surface error，不靜默 fallback

選擇：
- `ensure_mixed_wav` raise `MixerError` 種類：missing input、IOError、numpy error
- Handler 對應到 HTTP error codes：
  - `recording.mixed_not_applicable` (404) — single-channel meeting
  - `recording.mix_failed` (500) — IOError / numpy error
- Frontend `localizedErrorMessage` 顯示 inline alert；toggle UI **不自動切回 me-only**（user 必須手動切才知道對方那邊有 bug）

**理由**
- 靜默 fallback 會讓 user 以為 mixed 是壞的、其實對方在播時還是聽不到（誤導）
- 顯式 error + 手動 toggle 切換是 deliberate 行為

## Risks / Trade-offs

- **Risk**：60-min meeting first-mix 等 1-2 秒，user 沒 UI feedback 會以為按了沒反應
  - **Mitigation**：mini-player 在 audio 元素 `loadstart` ~ `canplay` 之間顯示 spinner overlay（既有 mini-player 沒這 UI、加一個小 spinner）
- **Risk**：concurrent first-play 兩個 worker 同時跑 mix
  - **Mitigation**：寫 `mixed.wav.tmp` → atomic rename；同一個檔可能被 mix 兩次但最後檔內容一致、無 corrupt
- **Risk**：`me.wav` / `counterparty.wav` 長度差很多（一邊 60min、另一邊 5sec）—— mix 結果大部分時間只一邊有聲
  - **Trade-off**：接受。這種 case 通常表示其中一個 stream finalize 失敗、user 應該被 fallback toggle 看到原 stream

## Migration Plan

無 schema migration。
1. Backend deploy：新 endpoint + mixer module；既有 per-recording endpoint 不動
2. Frontend deploy：mini-player 升級為 toggle UI，預設 mixed
3. 既有 meeting 的 `mixed.wav` 在使用者第一次按播放時被 lazy 建立；沒人按就不建（不浪費 disk）

## Open Questions

(none — design 階段都決定完)

## Implementation Contract

- 新檔 `packages/backend/meeting_playbook/audio_playback/mixer.py` exports:
  - `mix_pcm_int16(left: bytes, right: bytes) -> bytes` — equal-length int16 PCM avg
  - `ensure_mixed_wav(meeting_id: str, recordings_dir: Path) -> Path` — lazy, idempotent
  - exceptions `MixerInputMissing` (一邊 wav 不存在) + `MixerError` (IOError / numpy)
- 新 endpoint `GET /api/meetings/{id}/recordings/mixed/audio` 接 `?start=&end=` 跟既有 per-recording endpoint 同 query schema；回 `audio/wav`、honor HTTP Range
- Single-channel meeting (`me.wav` 或 `counterparty.wav` 不存在) → 404 `recording.mixed_not_applicable`
- Mix IO / numpy 失敗 → 500 `recording.mix_failed`
- `<MeetingAudioMiniPlayer>` 加 `data-testid="mini-player-source-toggle"` segment 三 button (`source-mixed` / `source-me` / `source-counterparty`)
- Source toggle 行為：切換時 reload `<audio>.src` 為新 source URL、`onLoadedMetadata` 回填 `currentTime`、保 `paused` / `playbackRate`
- `localStorage.miniPlayerSource` 鍵：`"mixed" | "me" | "counterparty"`，default `"mixed"`
- `pickMeetingRecording(recordings)` 升級 return shape：`{ kind: "dual" | "single", sources: { mixed?, me?, counterparty? }, defaultSource: "mixed" | "me" }`（dual 三個都有、single 只 `me`）
- Toggle UI 在 `kind === "single"` 時 **不 render**
- Mix endpoint failure → mini-player 顯示 `<Alert>` localized error；UI 不自動切回 me-only
- 新 i18n keys: `meeting.detail.audioPlayer.source.{mixed,me,counterparty}` + `errors.recording.{mixed_not_applicable,mix_failed}`，雙 locale 同步

## Scope Boundaries

**In scope**
- Backend `meeting_playbook/audio_playback/mixer.py` 新模組
- Backend `audio_playback/router.py` 新加 mixed endpoint handler
- Frontend `<MeetingAudioMiniPlayer>` 加 source toggle + 改 default source
- Frontend `pickMeetingRecording` return shape 升級
- Frontend `meetings-api.ts` 新加 mixed URL helper
- i18n keys for toggle UI + 兩個 error codes
- Tests：mixer unit + router integration + mini-player toggle tests

**Out of scope**
- 既有 per-recording endpoint / `parse_wav_header` / `compute_byte_range` 邏輯
- Sessions / capture / recording row creation
- Single-channel 錄音入口 UI（S27 範圍）
- Web Audio API / client-side mix
- 個別 stream 音量平衡 / RMS normalization
- Stereo (L/R) output
- Pre-compute on finalize
- Retention sweep / TTL 邏輯
- Playbook / Summary / Tactical advisor 任何邏輯
- Chunk slicing 語意
