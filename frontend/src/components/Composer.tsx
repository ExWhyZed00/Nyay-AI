"use client";

import { useRef, useState } from "react";
import { LANGUAGES } from "@/lib/types";

const MAX_CHARS = 1500;

type Props = {
  busy: boolean;
  language: string;
  onLanguage: (value: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
};

export default function Composer({ busy, language, onLanguage, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  function resize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function submit() {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
    requestAnimationFrame(resize);
  }

  return (
    <div className="border-t border-line bg-panel px-3 pb-3 pt-3 md:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2">
          <textarea
            ref={ref}
            value={text}
            rows={1}
            maxLength={MAX_CHARS}
            placeholder="Ask in any language, for example: what is the punishment for theft?"
            aria-label="Your question"
            onChange={(e) => {
              setText(e.target.value);
              resize();
            }}
            onKeyDown={(e) => {
              // Enter sends. Shift+Enter makes a new line. Do not send while an input method is composing text.
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            className="max-h-40 min-h-[2.75rem] flex-1 resize-none rounded-xl border border-line bg-paper px-3 py-2.5 leading-relaxed outline-none focus:border-brand"
          />
          {busy ? (
            <button
              type="button"
              onClick={onStop}
              className="h-11 rounded-xl border border-line px-4 text-sm font-medium"
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={!text.trim()}
              className="h-11 rounded-xl bg-brand px-4 text-sm font-medium text-brand-ink disabled:opacity-50"
            >
              Send
            </button>
          )}
        </div>

        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
          <label className="flex items-center gap-2">
            Answer language
            <select
              value={language}
              onChange={(e) => onLanguage(e.target.value)}
              className="rounded-md border border-line bg-paper px-2 py-1 text-ink"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          {text.length > MAX_CHARS - 200 && (
            <span>
              {text.length}/{MAX_CHARS}
            </span>
          )}
        </div>
        <p className="mt-2 text-xs text-muted">
          General information about the BNS, BNSS and the Constitution of India. Not legal advice. For your own case,
          speak to a lawyer or your District Legal Services Authority.
        </p>
      </div>
    </div>
  );
}
