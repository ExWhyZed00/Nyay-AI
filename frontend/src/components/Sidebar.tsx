"use client";

import type { Conversation } from "@/lib/types";
import { LogoutIcon, PanelIcon, PencilIcon, TrashIcon } from "./icons";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  email: string;
  mobileOpen: boolean;
  desktopOpen: boolean;
  onCollapse: () => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onSignOut: () => void;
};

export default function Sidebar({
  conversations,
  activeId,
  email,
  mobileOpen,
  desktopOpen,
  onCollapse,
  onNew,
  onSelect,
  onDelete,
  onSignOut,
}: Props) {
  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-20 bg-black/40 md:hidden" onClick={onCollapse} aria-hidden="true" />}

      {/* Phone: slides in over the page. Desktop: sits beside the chat and collapses to nothing. */}
      <aside
        aria-label="Your chats"
        className={`fixed inset-y-0 left-0 z-30 w-72 border-r border-line bg-sidebar transition-[transform,visibility] duration-200 motion-reduce:transition-none md:relative md:z-auto md:translate-x-0 md:overflow-hidden md:transition-[width,visibility] ${
          mobileOpen ? "translate-x-0" : "-translate-x-full max-md:invisible"
        } ${desktopOpen ? "md:w-72" : "md:invisible md:w-0 md:border-r-0"}`}
      >
        <div className="flex h-full w-72 flex-col">
          <div className="flex items-center justify-between px-4 py-3">
            <span className="text-base font-semibold tracking-tight">Nyay AI</span>
            <button
              type="button"
              onClick={onCollapse}
              aria-label="Close sidebar"
              title="Close sidebar"
              className="grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-hover hover:text-ink"
            >
              <PanelIcon />
            </button>
          </div>

          <div className="px-3 pb-2">
            <button
              type="button"
              onClick={onNew}
              className="flex w-full items-center gap-2.5 rounded-xl border border-line bg-panel px-3 py-2.5 text-sm font-medium hover:bg-hover"
            >
              <PencilIcon />
              New chat
            </button>
          </div>

          <p className="px-5 pb-1 pt-3 text-xs font-medium text-muted">Recent chats</p>

          <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-2" aria-label="Recent chats">
            {conversations.length === 0 ? (
              <p className="px-3 py-3 text-sm text-muted">Your chats will appear here.</p>
            ) : (
              <ul className="space-y-0.5">
                {conversations.map((c) => (
                  <li key={c.id} className="group relative">
                    <button
                      type="button"
                      onClick={() => onSelect(c.id)}
                      aria-current={c.id === activeId ? "page" : undefined}
                      className={`w-full truncate rounded-lg px-3 py-2 pr-10 text-left text-sm ${
                        c.id === activeId ? "bg-hover font-medium" : "text-ink/90 hover:bg-hover"
                      }`}
                    >
                      {c.title}
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(c.id)}
                      aria-label={`Delete chat: ${c.title}`}
                      title="Delete chat"
                      className="absolute right-1 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-muted hover:text-danger md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                    >
                      <TrashIcon />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </nav>

          <div className="flex items-center gap-3 border-t border-line px-4 py-3">
            <span
              aria-hidden="true"
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand text-sm font-semibold uppercase text-brand-ink"
            >
              {email.charAt(0) || "?"}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm" title={email}>
              {email}
            </span>
            <button
              type="button"
              onClick={onSignOut}
              aria-label="Log out"
              title="Log out"
              className="grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-hover hover:text-ink"
            >
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
