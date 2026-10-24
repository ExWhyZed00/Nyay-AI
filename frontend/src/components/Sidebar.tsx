"use client";

import type { Conversation } from "@/lib/types";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  email: string;
  open: boolean;
  onClose: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onSignOut: () => void;
};

export default function Sidebar({
  conversations,
  activeId,
  email,
  open,
  onClose,
  onNew,
  onSelect,
  onDelete,
  onSignOut,
}: Props) {
  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-black/40 md:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-line bg-panel transition-transform md:static md:translate-x-0 motion-reduce:transition-none ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Your chats"
      >
        <div className="p-3">
          <button
            type="button"
            onClick={onNew}
            className="w-full rounded-lg bg-brand px-3 py-2 text-sm font-medium text-brand-ink"
          >
            New chat
          </button>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted">Your chats will appear here.</p>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((c) => (
                <li key={c.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(c.id)}
                    aria-current={c.id === activeId ? "page" : undefined}
                    className={`w-full truncate rounded-lg px-3 py-2 pr-9 text-left text-sm ${
                      c.id === activeId ? "bg-brand/10 font-medium" : "hover:bg-paper"
                    }`}
                  >
                    {c.title}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(c.id)}
                    aria-label={`Delete chat: ${c.title}`}
                    className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-muted opacity-100 hover:text-danger md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="border-t border-line p-3 text-sm">
          <p className="truncate text-muted" title={email}>
            {email}
          </p>
          <button type="button" onClick={onSignOut} className="mt-1 font-medium text-brand underline underline-offset-2">
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
