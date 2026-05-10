/**
 * markdown-export — slice-10 helper for "匯出 .md" button.
 *
 * Per design.md Decision 7: File System Access API (Chrome / Edge 124+)
 * gives the user a native "save to..." dialog so the file lands at the
 * path they pick. Browsers without the API fall back to a blob download
 * to the default Downloads folder. AbortError (user cancelled the save
 * dialog) is respected — we DON'T fall back, because that would surprise
 * the user with an unexpected download.
 */

const _UNSAFE_FILENAME_CHARS = /[/\\:*?"<>|]/g;

interface MeetingShape {
  title: string;
  /** ISO8601 timestamp; only the date portion (YYYY-MM-DD) is used. */
  created_at: string;
}

export function buildExportFilename(meeting: MeetingShape): string {
  const safeTitle = meeting.title.replace(_UNSAFE_FILENAME_CHARS, "_");
  const datePart = meeting.created_at.slice(0, 10);
  return `${safeTitle}-${datePart}.md`;
}

declare global {
  interface Window {
    showSaveFilePicker?: (opts: {
      suggestedName: string;
      types?: { description: string; accept: Record<string, string[]> }[];
    }) => Promise<FileSystemFileHandle>;
  }
}

export async function exportSummaryAsMarkdown(
  meeting: MeetingShape,
  markdown: string,
): Promise<void> {
  const filename = buildExportFilename(meeting);

  if (typeof window !== "undefined" && typeof window.showSaveFilePicker === "function") {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: "Markdown", accept: { "text/markdown": [".md"] } }],
      });
      const writable = await (
        handle as unknown as { createWritable: () => Promise<FileSystemWritableFileStream> }
      ).createWritable();
      await writable.write(markdown);
      await writable.close();
      return;
    } catch (err) {
      // User cancelled the native save dialog — DO NOT fall back to
      // download (would surprise them). Any other error falls through
      // to the blob path so the user still gets the file.
      if ((err as DOMException)?.name === "AbortError") return;
    }
  }

  // Blob download fallback (Firefox, Safari, older Chrome, headless tests).
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
