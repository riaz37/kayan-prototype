import { Fragment, type ReactNode } from "react";

// **bold**, *italic* / _italic_, `code` — the light markup the agent and WhatsApp use.
const PATTERN = /(\*\*[^*\n]+\*\*|(?<![\w*])\*[^*\n]+\*(?![\w*])|_[^_\n]+_|`[^`\n]+`)/g;

/**
 * Render message text with WhatsApp-style emphasis. Everything is rendered as
 * React elements (never HTML), so message content cannot inject markup.
 */
export function formatMessage(text: string): ReactNode {
  return text.split(PATTERN).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if ((part.startsWith("*") && part.endsWith("*")) || (part.startsWith("_") && part.endsWith("_"))) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="rounded bg-black/10 px-1 py-0.5 text-[12px]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}
