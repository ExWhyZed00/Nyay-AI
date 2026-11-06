"use client";

import { useRef, useState } from "react";
import { LANGUAGES } from "@/lib/types";
import { ArrowUpIcon, StopIcon } from "./icons";

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
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  function submit() {
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
    requestAnimationFrame(resize);
  }

  return (
    <div>
      <div className="rounded-3xl border border-line bg-panel shadow-sm focus-within:border-muted">
        <textarea
          ref={ref}
          value={text}
          rows={1}
          maxLength={MAX_CHARS}
          placeholder="Ask about Indian law, in any language"
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
          className="block max-h-52 min-h-[3.5rem] w-full resize-none bg-transparent px-5 pb-1 pt-4 leading-relaxed outline-none placeholder:text-muted"
        />

        <div className="flex items-center justify-between gap-2 px-3 pb-3 pt-1">
          <label className="flex items-center gap-2 text-xs text-muted">
            <span className="hidden sm:inline">Answer language</span>
            <select
              value={language}
              onChange={(e) => onLanguage(e.target.value)}
              aria-label="Answer language"
              className="rounded-full border border-line bg-paper px-3 py-1.5 text-xs text-ink"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-center gap-3">
            {text.length > MAX_CHARS - 200 && (
              <span className="text-xs text-muted">
                {text.length}/{MAX_CHARS}
              </span>
            )}
            {busy ? (
              <button
                type="button"
                onClick={onStop}
                aria-label="Stop"
                title="Stop"
                className="grid h-9 w-9 place-items-center rounded-full bg-brand text-brand-ink"
              >
                <StopIcon />
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!text.trim()}
                aria-label="Send"
                title="Send"
                className="grid h-9 w-9 place-items-center rounded-full bg-brand text-brand-ink disabled:opacity-30"
              >
                <ArrowUpIcon />
              </button>
            )}
          </div>
        </div>
      </div>

      <p className="mt-3 px-3 text-center text-xs leading-relaxed text-muted">
        General information about the BNS, BNSS and the Constitution of India. Not legal advice. For your own case,
        speak to a lawyer or your District Legal Services Authority.
      </p>
    </div>
  );
}
