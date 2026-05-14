/**
 * Encode a browser-recorded audio blob (WebM/Opus on Chrome, MP4/AAC on
 * Safari) into a 16kHz mono 16-bit PCM WAV blob.
 *
 * Slice-13: the backend's `compute_enrollment_embedding` feeds the WAV
 * directly into the pyannote pipeline, and the validation layer uses the
 * Python `wave` stdlib to read the duration — both require a real WAV
 * header. `MediaRecorder` does not output WAV natively in any browser, so
 * we re-encode in the browser via the Web Audio API.
 *
 * Pipeline:
 *   1. Read the blob's ArrayBuffer.
 *   2. `AudioContext.decodeAudioData` → `AudioBuffer` (decoded PCM).
 *   3. `OfflineAudioContext` at 16kHz, single channel — resamples + downmixes.
 *   4. Take `getChannelData(0)` → `Float32Array` in [-1.0, 1.0].
 *   5. Quantize to Int16 + prepend a 44-byte PCM WAV header.
 */

const _TARGET_SAMPLE_RATE = 16_000;
const _TARGET_CHANNELS = 1;
const _BITS_PER_SAMPLE = 16;

export async function encodeWavFromBlob(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();

  // Modern browsers expose `AudioContext`; Safari aliases it under
  // `webkitAudioContext` in older versions. Cast through `any` to dodge
  // the TypeScript lib's missing prefix.
  const AudioContextCtor: typeof AudioContext =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).AudioContext ?? (globalThis as any).webkitAudioContext;
  if (!AudioContextCtor) {
    throw new Error("AudioContext is not available in this browser");
  }

  const decodingContext = new AudioContextCtor();
  let decoded: AudioBuffer;
  try {
    decoded = await decodingContext.decodeAudioData(arrayBuffer.slice(0));
  } finally {
    // The decoding context is only needed to parse the input; close it
    // so the browser can release the audio worker thread.
    await decodingContext.close().catch(() => {});
  }

  // Resample + downmix via an OfflineAudioContext at the target rate.
  const targetFrameCount = Math.ceil(decoded.duration * _TARGET_SAMPLE_RATE);
  const offline = new OfflineAudioContext(_TARGET_CHANNELS, targetFrameCount, _TARGET_SAMPLE_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start(0);
  const resampled = await offline.startRendering();

  const pcm = resampled.getChannelData(0);
  return _encodeWavBlob(pcm);
}

/**
 * Convert a Float32 PCM sample array to a 16-bit PCM WAV blob (mono, 16kHz).
 * Exported for unit testing — the resampling pipeline is tested separately
 * via the integration flow.
 */
export function _encodeWavBlob(pcm: Float32Array): Blob {
  const byteRate = _TARGET_SAMPLE_RATE * _TARGET_CHANNELS * (_BITS_PER_SAMPLE / 8);
  const blockAlign = _TARGET_CHANNELS * (_BITS_PER_SAMPLE / 8);
  const dataSize = pcm.length * (_BITS_PER_SAMPLE / 8);

  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  _writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, /* littleEndian= */ true);
  _writeAscii(view, 8, "WAVE");
  _writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true); // subchunk1 size (PCM)
  view.setUint16(20, 1, true); // audio format PCM
  view.setUint16(22, _TARGET_CHANNELS, true);
  view.setUint32(24, _TARGET_SAMPLE_RATE, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, _BITS_PER_SAMPLE, true);
  _writeAscii(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (const sample of pcm) {
    // Clamp + scale Float32 [-1.0, 1.0] to Int16 [-32768, 32767].
    const clamped = Math.max(-1, Math.min(1, sample));
    const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(offset, int16, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function _writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}
