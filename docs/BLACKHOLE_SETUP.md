# BlackHole 2ch Setup (macOS)

Slice 7 captures **two** audio streams during a meeting:

- **`me`** — your microphone (system input default)
- **`counterparty`** — system audio routed through BlackHole 2ch

Until you complete the setup below, only the microphone stream works.
Pre-flight will refuse to start a session if BlackHole is missing.

> ADR-0004 chose BlackHole over alternatives (ScreenCaptureKit Swift helper,
> browser `getDisplayMedia`) because it works for every meeting app on macOS
> with one-time configuration.

---

## ⚠️ Important — Use headphones during meetings

The Multi-Output Device routes meeting audio to **both** your speakers
(so you can hear) **and** BlackHole (so we can record the counterparty).
If you don't wear headphones, your microphone will pick up everything the
speakers play, and **`me.wav` will contain the same audio as
`counterparty.wav`** — both transcripts end up nearly identical.

There is no software fix for this in slice-7; the project explicitly does
not implement DSP echo cancellation. The user-facing mitigation is:

- **Wear wired or wireless headphones** during any recorded meeting. The
  speakers go silent, the mic only hears you, the two streams stay clean.
- A reminder banner above the **Start Meeting** button on the detail page
  surfaces this every time you open a `scheduled` meeting.

If you forget the headphones during a real meeting, the resulting
recording is still useful (counterparty stream is still correct), but
your own transcript will be polluted with the counterparty's words.

---

## 1. Install BlackHole 2ch

```sh
brew install blackhole-2ch
```

Then verify the device shows up:

```sh
cd packages/backend && uv run python -c "
import sounddevice as sd
for i, d in enumerate(sd.query_devices()):
    if d['max_input_channels'] > 0:
        print(f\"{i}: {d['name']} (in={d['max_input_channels']})\")
"
```

You should see a row like:

```
2: BlackHole 2ch (in=2)
```

If not, restart your Mac (Core Audio sometimes needs a reload to pick up the
new driver) and re-run.

---

## 2. Create a Multi-Output Device

Open **Audio MIDI Setup** (`/Applications/Utilities/Audio MIDI Setup.app` or
Spotlight search "Audio MIDI Setup").

1. Click the **`+`** button (bottom-left) → **Create Multi-Output Device**.
2. In the right panel, check the **Use** column for:
   - ✅ Your speakers / headphones (so you can hear the meeting)
   - ✅ **BlackHole 2ch** (so Python can record system audio)
3. **Primary Device** dropdown → select your speakers / headphones.
   - **NOT BlackHole** — using BlackHole as primary causes clock drift and
     out-of-sync audio.
4. ✅ Check **Drift Correction** on the **BlackHole 2ch** row (NOT on the
   primary device row). Drift correction keeps the secondary device's clock
   aligned with the primary.
5. Rename the new device by double-clicking it in the left panel (e.g.
   `Meeting Output`).

---

## 3. Set Meeting Output as the system Output device

Two ways:

- **Quick toggle** — `Option`-click the speaker icon in the menu bar →
  **Output** section → choose `Meeting Output`.
- **System Settings** — `Sound → Output → Meeting Output`.

After switching, play a YouTube video or any audio. You should hear it
normally **and** see the BlackHole 2ch input level moving in
**System Settings → Sound → Input → BlackHole 2ch**.

---

## 4. Per-meeting-app speaker selection

Each meeting app overrides the system output. Select **Meeting Output** as
the speaker inside each app you use:

- **Zoom** — `Settings → Audio → Speaker → Meeting Output`. Microphone stays
  whatever you normally use (built-in / external mic).
- **Microsoft Teams** — `Settings → Devices → Speaker → Meeting Output`.
- **Google Meet** (Chrome) — during a call: 三點選單 → `Settings → Audio →
  Speaker → Meeting Output`.
- **FaceTime** — during a call, the audio output picker in the menu bar →
  Meeting Output.

---

## Common gotchas

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| You hear nothing at all | Primary Device is set to BlackHole instead of your speakers | Step 2.3 — switch primary to your speakers |
| Echo / reverb during a call OR `me.wav` and `counterparty.wav` end up identical | Mic is picking up the speaker output (no headphones) | **See top-of-doc callout** — wear headphones |
| Slice 7 says `BlackHole stream silent for 30s` | Multi-Output Device not selected as system Output | Step 3 — switch system output to Meeting Output |
| BlackHole row missing in Audio MIDI Setup | Driver didn't load | Restart Mac |
| Audio app overrides Output back | Each app has its own Speaker setting | Step 4 — set Meeting Output per app |

---

## Optional: env-var overrides

If you have multiple BlackHole versions installed (2ch + 16ch) or want to
use a non-default microphone, set these in `.env`:

```sh
BLACKHOLE_DEVICE_NAME=BlackHole 16ch
MIC_DEVICE_NAME=My Specific Microphone
```

The values must match the device name reported by
`sounddevice.query_devices()` exactly. Default (unset) → auto-detect by name
pattern + system input default.
