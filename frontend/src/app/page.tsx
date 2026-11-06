"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Composer from "@/components/Composer";
import MessageView from "@/components/MessageView";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import { PanelIcon, PencilIcon } from "@/components/icons";
import {
  ApiError,
  deleteConversation,
  errorMessage,
  getMessages,
  listConversations,
  streamChat,
} from "@/lib/api";
import { getAccessToken, getSupabase } from "@/lib/supabase";
import { STATUS_LABELS, type ChatEvent, type Conversation, type Message } from "@/lib/types";

const EXAMPLES = [
  "What rights do I have if I am arrested?",
  "चोरी की सज़ा क्या है?",
  "காவல்துறை வாரண்ட் இல்லாமல் கைது செய்ய முடியுமா?",
  "জামিন কী এবং কখন পাওয়া যায়?",
];

export default function ChatPage() {
  const router = useRouter();

  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [language, setLanguage] = useState("auto");
  const [mobileOpen, setMobileOpen] = useState(false); // phone: drawer over the page
  const [desktopOpen, setDesktopOpen] = useState(true); // desktop: sidebar beside the chat
  const [loadingChat, setLoadingChat] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const setActive = useCallback((id: string | null) => {
    activeIdRef.current = id;
    setActiveId(id);
  }, []);

  const goToLogin = useCallback(() => router.replace("/login"), [router]);

  // ---- login gate ----------------------------------------------------------------
  useEffect(() => {
    let supabase;
    try {
      supabase = getSupabase();
    } catch (e) {
      setNotice(errorMessage(e));
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        goToLogin();
      } else {
        setEmail(data.session.user.email ?? "");
        setReady(true);
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) goToLogin();
    });
    return () => sub.subscription.unsubscribe();
  }, [goToLogin]);

  const handleApiError = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) {
        goToLogin();
        return;
      }
      setNotice(errorMessage(e));
    },
    [goToLogin]
  );

  const refreshConversations = useCallback(async () => {
    try {
      const token = await getAccessToken();
      if (!token) return;
      setConversations(await listConversations(token));
    } catch (e) {
      handleApiError(e);
    }
  }, [handleApiError]);

  useEffect(() => {
    if (ready) refreshConversations();
  }, [ready, refreshConversations]);

  // keep the newest message in view
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status]);

  // ---- actions --------------------------------------------------------------------
  function stop() {
    abortRef.current?.abort();
  }

  function newChat() {
    stop();
    setActive(null);
    setMessages([]);
    setNotice(null);
    setLoadingChat(false);
    setMobileOpen(false);
  }

  async function selectConversation(id: string) {
    stop();
    setMobileOpen(false);
    setNotice(null);
    setActive(id);
    setMessages([]);
    setLoadingChat(true);
    try {
      const token = await getAccessToken();
      if (!token) return goToLogin();
      const rows = await getMessages(token, id);
      if (activeIdRef.current !== id) return; // user clicked something else meanwhile
      setMessages(
        rows.map((r) => ({
          id: `m${r.id}`,
          role: r.role,
          content: r.content,
          sources: r.sources ?? [],
          verified: r.verified,
        }))
      );
    } catch (e) {
      handleApiError(e);
    } finally {
      if (activeIdRef.current === id) setLoadingChat(false);
    }
  }

  async function removeConversation(id: string) {
    if (!window.confirm("Delete this chat? This cannot be undone.")) return;
    try {
      const token = await getAccessToken();
      if (!token) return goToLogin();
      await deleteConversation(token, id);
      if (activeIdRef.current === id) newChat();
      await refreshConversations();
    } catch (e) {
      handleApiError(e);
    }
  }

  async function signOut() {
    stop();
    await getSupabase().auth.signOut();
    goToLogin();
  }

  async function send(text: string) {
    if (busy) return;
    const token = await getAccessToken();
    if (!token) return goToLogin();

    const stamp = Date.now();
    const botId = `a${stamp}`;
    setMessages((list) => [
      ...list,
      { id: `u${stamp}`, role: "user", content: text, sources: [], verified: null },
      { id: botId, role: "assistant", content: "", sources: [], verified: null, streaming: true },
    ]);
    setBusy(true);
    setStatus("connecting");
    setNotice(null);

    const controller = new AbortController();
    abortRef.current = controller;
    // Free hosting sleeps when idle. Tell the user why the first answer is slow.
    const wakeTimer = setTimeout(() => setStatus((s) => (s === "connecting" ? "waking" : s)), 8000);

    const patchBot = (fn: (m: Message) => Message) =>
      setMessages((list) => list.map((m) => (m.id === botId ? fn(m) : m)));

    const onEvent = (ev: ChatEvent) => {
      clearTimeout(wakeTimer);
      switch (ev.type) {
        case "meta":
          setActive(ev.conversation_id);
          break;
        case "status":
          setStatus(ev.step);
          break;
        case "reset":
          patchBot((m) => ({ ...m, content: "" }));
          break;
        case "token":
          patchBot((m) => ({ ...m, content: m.content + ev.text }));
          break;
        case "done":
          patchBot((m) => ({ ...m, sources: ev.sources, verified: ev.verified, streaming: false }));
          break;
        case "error":
          patchBot((m) => ({ ...m, streaming: false, error: ev.message }));
          break;
      }
    };

    try {
      await streamChat(
        token,
        { message: text, conversation_id: activeIdRef.current, language },
        onEvent,
        controller.signal
      );
    } catch (e) {
      if (!controller.signal.aborted) {
        if (e instanceof ApiError && e.status === 401) {
          goToLogin();
        } else {
          patchBot((m) => ({ ...m, error: errorMessage(e) }));
        }
      }
    } finally {
      clearTimeout(wakeTimer);
      patchBot((m) => ({ ...m, streaming: false }));
      setBusy(false);
      setStatus(null);
      abortRef.current = null;
      refreshConversations();
    }
  }

  const collapseSidebar = () => {
    setMobileOpen(false);
    setDesktopOpen(false);
  };
  const openSidebar = () => {
    setMobileOpen(true);
    setDesktopOpen(true);
  };

  // ---- screen ---------------------------------------------------------------------
  if (!ready) {
    return (
      <main className="flex h-full items-center justify-center px-4 text-center text-muted">
        {notice ? <p role="alert" className="max-w-md text-danger">{notice}</p> : <p>Loading…</p>}
      </main>
    );
  }

  // New-chat mode: no chat open and nothing typed yet. The chat box is centred on the page.
  const isEmpty = messages.length === 0 && activeId === null;
  const iconButton = "grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-hover hover:text-ink";
  // These two buttons show on phones always, and on desktop only while the sidebar is collapsed.
  const collapsedOnly = desktopOpen ? "md:hidden" : "";

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        email={email}
        mobileOpen={mobileOpen}
        desktopOpen={desktopOpen}
        onCollapse={collapseSidebar}
        onNew={newChat}
        onSelect={selectConversation}
        onDelete={removeConversation}
        onSignOut={signOut}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between px-3 py-3 md:px-5">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={openSidebar}
              aria-label="Open sidebar"
              title="Open sidebar"
              className={`${iconButton} ${collapsedOnly}`}
            >
              <PanelIcon />
            </button>
            <button
              type="button"
              onClick={newChat}
              aria-label="New chat"
              title="New chat"
              className={`${iconButton} ${collapsedOnly}`}
            >
              <PencilIcon />
            </button>
            <span className="ml-1 font-semibold tracking-tight md:hidden">Nyay AI</span>
          </div>
          <ThemeToggle />
        </header>

        <div className={`flex min-h-0 flex-1 flex-col ${isEmpty ? "justify-center" : ""}`}>
          {isEmpty ? (
            <h1 className="px-4 pb-8 text-center text-3xl font-medium tracking-tight md:text-4xl">
              Hello, how can I help?
            </h1>
          ) : (
            <main className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
              <div className="mx-auto max-w-3xl space-y-8">
                {notice && (
                  <p role="alert" className="rounded-xl border border-danger/40 px-3 py-2 text-sm text-danger">
                    {notice}
                  </p>
                )}
                {loadingChat && messages.length === 0 && <p className="text-sm text-muted">Loading chat…</p>}
                {messages.map((m) => (
                  <MessageView
                    key={m.id}
                    message={m}
                    statusLabel={status ? (STATUS_LABELS[status] ?? null) : null}
                  />
                ))}
                <div ref={bottomRef} />
              </div>
            </main>
          )}

          <div className={isEmpty ? "mx-auto w-full max-w-2xl px-4 pb-24" : "px-3 pb-4 pt-2 md:px-6"}>
            <div className={isEmpty ? "" : "mx-auto max-w-3xl"}>
              {isEmpty && notice && (
                <p role="alert" className="mb-3 rounded-xl border border-danger/40 px-3 py-2 text-sm text-danger">
                  {notice}
                </p>
              )}
              <Composer busy={busy} language={language} onLanguage={setLanguage} onSend={send} onStop={stop} />
              {isEmpty && (
                <ul className="mt-5 flex flex-wrap justify-center gap-2">
                  {EXAMPLES.map((q) => (
                    <li key={q}>
                      <button
                        type="button"
                        onClick={() => send(q)}
                        className="rounded-full border border-line px-3.5 py-1.5 text-sm text-muted hover:bg-hover hover:text-ink"
                      >
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
