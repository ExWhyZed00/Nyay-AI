"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Message } from "@/lib/types";

type Props = {
  message: Message;
  statusLabel: string | null;
};

/** Turns "[1]" into a markdown link "[1](#cite-1)" that we render as a small citation chip. */
function linkCitations(text: string): string {
  return text.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");
}

export default function MessageView({ message, statusLabel }: Props) {
  const [openSource, setOpenSource] = useState<number | null>(null);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-brand-ink [overflow-wrap:anywhere]">
          {message.content}
        </p>
      </div>
    );
  }

  const active = message.sources.find((s) => s.n === openSource);

  return (
    <div className="max-w-[46rem]">
      {message.content && (
        <div className="answer">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const m = href?.match(/^#cite-(\d+)$/);
                if (m) {
                  const n = Number(m[1]);
                  const src = message.sources.find((s) => s.n === n);
                  return (
                    <button
                      type="button"
                      className="cite"
                      title={src?.ref}
                      aria-label={src ? `Source ${n}: ${src.ref}` : `Source ${n}`}
                      onClick={() => setOpenSource((cur) => (cur === n ? null : n))}
                    >
                      {n}
                    </button>
                  );
                }
                return (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand underline">
                    {children}
                  </a>
                );
              },
            }}
          >
            {linkCitations(message.content)}
          </ReactMarkdown>
        </div>
      )}

      {message.streaming && statusLabel && (
        <p role="status" aria-live="polite" className="mt-2 text-sm text-muted motion-safe:animate-pulse">
          {statusLabel}
        </p>
      )}

      {message.error && (
        <p role="alert" className="mt-2 rounded-lg border border-danger/40 px-3 py-2 text-sm text-danger">
          {message.error}
        </p>
      )}

      {!message.streaming && message.verified === true && (
        <p className="mt-3 text-sm text-ok">✓ Checked against the sources</p>
      )}
      {!message.streaming && message.verified === false && (
        <p className="mt-3 text-sm text-warn">
          Could not fully verify this answer. Please read the sources below before relying on it.
        </p>
      )}

      {!message.streaming && message.sources.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-muted">Sources</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {message.sources.map((s) => (
              <button
                key={s.n}
                type="button"
                onClick={() => setOpenSource((cur) => (cur === s.n ? null : s.n))}
                aria-expanded={openSource === s.n}
                className={`rounded-lg border px-2.5 py-1 text-sm ${
                  openSource === s.n ? "border-brass bg-brass-soft text-brass" : "border-line bg-panel"
                }`}
              >
                <span className="font-semibold text-brass">{s.n}</span> {s.ref}
              </button>
            ))}
          </div>
          {active && (
            <div className="mt-2 rounded-lg border border-line bg-panel p-3 text-sm">
              <p className="font-semibold">
                {active.ref}
                {active.title ? `: ${active.title}` : ""}
              </p>
              <p className="mt-1.5 leading-relaxed text-muted">
                {active.snippet}
                {active.snippet.length >= 400 ? "…" : ""}
              </p>
              {active.page ? <p className="mt-1.5 text-xs text-muted">Page {active.page} of the source PDF</p> : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
