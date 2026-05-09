/**
 * Locale-file integrity tests (AC-2, AC-9).
 *
 * Two invariants protected by these tests:
 *  1. Every locale file has the same key tree (no key may live in only one
 *     locale). This is the contract documented in CLAUDE.md.
 *  2. Both files contain the three top-level groups required by design:
 *     `common`, `auth`, `errors`.
 *
 * If a future PR adds a key to one locale but forgets the other, the
 * deep-equal check below fails before the change can land.
 */

import { describe, expect, test } from "bun:test";
import en from "./en.json";
import zhTW from "./zh-TW.json";

type AnyJson = Record<string, unknown>;

/** Recursively collect the set of dot-paths in a JSON object. */
function collectPaths(obj: unknown, prefix = ""): string[] {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return [prefix];
  }
  const o = obj as AnyJson;
  return Object.keys(o)
    .sort()
    .flatMap((k) => collectPaths(o[k], prefix ? `${prefix}.${k}` : k));
}

describe("locale files mirror each other", () => {
  test("both files have identical key trees", () => {
    const zhPaths = collectPaths(zhTW);
    const enPaths = collectPaths(en);
    expect(zhPaths).toEqual(enPaths);
  });

  test("meeting.session.* + errors.session.* namespaces present in both files", () => {
    const zhPaths = new Set(collectPaths(zhTW));
    const enPaths = new Set(collectPaths(en));
    const requiredKeys = [
      "meetings.session.start",
      "meetings.session.end",
      "meetings.session.capturing",
      "meetings.session.silenceWarning",
      "meetings.session.transcriptHeading",
      "meetings.session.transcriptEmpty",
      "errors.session.no_audio_device",
      "errors.session.bad_start",
      "errors.session.bad_status",
      "errors.session.persist_failed",
      "errors.session.unknown_message",
      "errors.session.connection_lost",
    ];
    for (const k of requiredKeys) {
      expect(zhPaths.has(k)).toBe(true);
      expect(enPaths.has(k)).toBe(true);
    }
  });

  test("calendar.* namespace covers heading / connect / row / errors in both files", () => {
    const zhPaths = new Set(collectPaths(zhTW));
    const enPaths = new Set(collectPaths(en));
    const requiredKeys = [
      "calendar.heading",
      "calendar.empty",
      "calendar.connect.cta",
      "calendar.connect.description",
      "calendar.row.attendees",
      "calendar.row.import",
      "calendar.row.importing",
      "errors.calendar.not_connected",
      "errors.calendar.token_expired",
      "errors.calendar.network_error",
      "errors.playbook.generation_timeout",
      "errors.playbook.generation_failed",
      "meetings.list.fromCalendarButton",
    ];
    for (const k of requiredKeys) {
      expect(zhPaths.has(k)).toBe(true);
      expect(enPaths.has(k)).toBe(true);
    }
  });

  test("playbook.* namespace covers toggle / fields / save / errors in both files", () => {
    const zhPaths = new Set(collectPaths(zhTW));
    const enPaths = new Set(collectPaths(en));
    const requiredKeys = [
      "playbook.heading",
      "playbook.toggle.freeform",
      "playbook.toggle.structured",
      "playbook.freeform.label",
      "playbook.fields.objective",
      "playbook.fields.counterpartyProfile",
      "playbook.fields.anticipatedTopics",
      "playbook.fields.anticipatedObjections",
      "playbook.fields.talkingPoints",
      "playbook.fields.redLines",
      "playbook.save.idle",
      "playbook.save.saving",
      "playbook.save.saved",
      "playbook.errors.fallback",
    ];
    for (const k of requiredKeys) {
      expect(zhPaths.has(k)).toBe(true);
      expect(enPaths.has(k)).toBe(true);
    }
  });

  test("meetings.* namespace covers list / new / detail / status in both files", () => {
    const zhPaths = new Set(collectPaths(zhTW));
    const enPaths = new Set(collectPaths(en));
    const requiredKeys = [
      "meetings.list.heading",
      "meetings.list.newButton",
      "meetings.list.empty",
      "meetings.new.heading",
      "meetings.new.titleLabel",
      "meetings.new.counterpartyLabel",
      "meetings.new.meLabel",
      "meetings.new.submit",
      "meetings.new.cancel",
      "meetings.new.errorFallback",
      "meetings.detail.heading",
      "meetings.detail.back",
      "meetings.detail.deleteButton",
      "meetings.detail.deleteDialogTitle",
      "meetings.detail.deleteConfirm",
      "meetings.detail.deleteCancel",
      "meetings.status.scheduled",
      "meetings.status.in_progress",
      "meetings.status.completed",
      "errors.meeting.not_found",
      "errors.meeting.title.required",
      "errors.meeting.counterparty_display_name.required",
      "errors.meeting.me_display_name.required",
    ];
    for (const k of requiredKeys) {
      expect(zhPaths.has(k)).toBe(true);
      expect(enPaths.has(k)).toBe(true);
    }
  });

  test("both files declare the required top-level groups (common/auth/errors plus domain groups)", () => {
    const required = new Set(["auth", "common", "errors"]);
    const zhKeys = new Set(Object.keys(zhTW as AnyJson));
    const enKeys = new Set(Object.keys(en as AnyJson));
    for (const k of required) {
      expect(zhKeys.has(k)).toBe(true);
      expect(enKeys.has(k)).toBe(true);
    }
    // Top-level groups must mirror — domain groups (e.g. "meetings") added to
    // one file MUST be added to the other; mirroring is enforced for safety.
    expect(Object.keys(zhTW as AnyJson).sort()).toEqual(Object.keys(en as AnyJson).sort());
  });
});
