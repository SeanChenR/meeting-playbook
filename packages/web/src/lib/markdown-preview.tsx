/**
 * MarkdownPreview — read-only rendered markdown for the playbook freeform tab.
 *
 * Slice-7 round 2: replaces the TipTap WYSIWYG editor (which felt heavy in
 * the narrow detail-page column). The freeform tab now ships a small
 * Edit/Preview sub-toggle; this component renders the Preview side.
 *
 * Pipeline: react-markdown + remark-gfm (tables, task lists, strikethrough,
 * autolinks) + rehype-sanitize (defense-in-depth — strips `<script>`, raw
 * `on*` event handlers, etc., even though Vertex Gemini output is normally
 * safe).
 */

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

export interface MarkdownPreviewProps {
  source: string;
}

export function MarkdownPreview({ source }: MarkdownPreviewProps) {
  return (
    <div data-testid="markdown-preview" className="prose prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
