"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Composer from "@/components/Composer";
import MessageView from "@/components/MessageView";
import Sidebar from "@/components/Sidebar";
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    setSidebarOpen(false);
  }

  async function selectConversation(id: string) {
    stop();
    setSidebarOpen(false);
    setNotice(null);
    setActive(id);
    setMessages([]);
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

  // ---- screen ---------------------------------------------------------------------
  if (!ready) {
    return (
      <main className="flex h-full items-center justify-center px-4 text-center text-muted">
        {notice ? <p role="alert" className="max-w-md text-danger">{notice}</p> : <p>Loading…</p>}
      </main>
    );
  }

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        email={email}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNew={newChat}
        onSelect={selectConversation}
        onDelete={removeConversation}
        onSignOut={signOut}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-panel px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open your chats"
            className="rounded-md border border-line px-2.5 py-1 text-sm"
          >
            Chats
          </button>
          <span className="font-semibold">Nyay AI</span>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto px-3 py-6 md:px-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {notice && (
              <p role="alert" className="rounded-lg border border-danger/40 px-3 py-2 text-sm text-danger">
                {notice}
              </p>
            )}

            {messages.length === 0 && (
              <section className="pt-6 md:pt-16">
                <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
                  Ask about Indian criminal law and your constitutional rights
                </h1>
                <p className="mt-2 max-w-xl text-muted">
                  Answers come only from the BNS, the BNSS and the Constitution of India, with the sections named so you
                  can check them.
                </p>
                <ul className="mt-6 grid gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((q) => (
                    <li key={q}>
                      <button
                        type="button"
                        onClick={() => send(q)}
                        className="w-full rounded-xl border border-line bg-panel px-4 py-3 text-left text-sm hover:border-brand"
                      >
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

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

        <Composer busy={busy} language={language} onLanguage={setLanguage} onSend={send} onStop={stop} />
      </div>
    </div>
  );
}
