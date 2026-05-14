/**
 * Unit tests for the WAV encoder's pure portion (`_encodeWavBlob`).
 *
 * The full pipeline (decodeAudioData + OfflineAudioContext resampling) needs
 * a real browser audio stack which happy-dom does not provide; that path is
 * covered indirectly by the component test (which mocks the encoder) and
 * exercised end-to-end during manual QA. Here we verify the WAV header
 * + PCM sample math, which is the part most likely to drift.
 */

import { describe, expect, test } from "bun:test";

import { _encodeWavBlob } from "./wav-encoder";

function _readUint32LE(view: DataView, offset: number): number {
  return view.getUint32(offset, true);
}

function _readUint16LE(view: DataView, offset: number): number {
  return view.getUint16(offset, true);
}

function _readAscii(view: DataView, offset: number, length: number): string {
  let s = "";
  for (let i = 0; i < length; i += 1) {
    s += String.fromCharCode(view.getUint8(offset + i));
  }
  return s;
}

describe("_encodeWavBlob", () => {
  test("emits a valid 44-byte PCM WAV header for 16kHz mono", async () => {
    const samples = new Float32Array(16_000); // 1 second of silence
    const blob = _encodeWavBlob(samples);

    expect(blob.type).toBe("audio/wav");
    const buffer = await blob.arrayBuffer();
    const view = new DataView(buffer);

    expect(_readAscii(view, 0, 4)).toBe("RIFF");
    expect(_readAscii(view, 8, 4)).toBe("WAVE");
    expect(_readAscii(view, 12, 4)).toBe("fmt ");
    expect(_readUint32LE(view, 16)).toBe(16); // PCM subchunk size
    expect(_readUint16LE(view, 20)).toBe(1); // PCM format
    expect(_readUint16LE(view, 22)).toBe(1); // channels
    expect(_readUint32LE(view, 24)).toBe(16_000); // sample rate
    expect(_readUint32LE(view, 28)).toBe(32_000); // byte rate = 16000 * 1 * 2
    expect(_readUint16LE(view, 32)).toBe(2); // block align
    expect(_readUint16LE(view, 34)).toBe(16); // bits per sample
    expect(_readAscii(view, 36, 4)).toBe("data");

    const dataSize = _readUint32LE(view, 40);
    expect(dataSize).toBe(16_000 * 2); // 16000 frames * 2 bytes
    // The RIFF size field is the file length minus the leading "RIFF" + size.
    expect(_readUint32LE(view, 4)).toBe(36 + dataSize);
  });

  test("clips out-of-range Float32 samples to Int16 boundaries", async () => {
    // Three samples: +2.0 (clamps high), -2.0 (clamps low), 0.0 (silence).
    const samples = new Float32Array([2.0, -2.0, 0.0]);
    const blob = _encodeWavBlob(samples);
    const view = new DataView(await blob.arrayBuffer());

    // First sample → clamped to +1.0 → Int16 0x7fff (32767)
    expect(view.getInt16(44, true)).toBe(0x7fff);
    // Second sample → clamped to -1.0 → Int16 -32768
    expect(view.getInt16(46, true)).toBe(-32_768);
    // Third sample → 0
    expect(view.getInt16(48, true)).toBe(0);
  });

  test("encodes the correct number of PCM bytes for non-empty input", async () => {
    const samples = new Float32Array([0.5, -0.5, 0.25, -0.25]);
    const blob = _encodeWavBlob(samples);

    // 44 header + 4 samples * 2 bytes
    expect(blob.size).toBe(44 + 8);
  });

  test("an empty input still produces a parseable header", async () => {
    const blob = _encodeWavBlob(new Float32Array(0));
    const view = new DataView(await blob.arrayBuffer());

    expect(blob.size).toBe(44);
    expect(_readUint32LE(view, 40)).toBe(0);
    expect(_readUint32LE(view, 4)).toBe(36);
  });
});
