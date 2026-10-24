"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Already logged in? Go straight to the chat.
  useEffect(() => {
    try {
      getSupabase()
        .auth.getSession()
        .then(({ data }) => {
          if (data.session) router.replace("/");
        });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup problem.");
    }
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    setBusy(true);
    try {
      const supabase = getSupabase();
      if (mode === "login") {
        const { error: err } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (err) throw err;
        router.replace("/");
      } else {
        const { data, error: err } = await supabase.auth.signUp({ email: email.trim(), password });
        if (err) throw err;
        if (data.session) {
          router.replace("/");
        } else {
          setInfo("Account created. Check your email and click the confirmation link, then log in here.");
          setMode("login");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <main className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-semibold tracking-tight">Nyay AI</h1>
        <p className="mt-2 text-muted">
          Ask about the BNS, the BNSS and the Constitution of India in Hindi, Tamil, Bengali and more. Every answer
          names the sections it comes from.
        </p>

        <form onSubmit={submit} className="mt-8 rounded-xl border border-line bg-panel p-6">
          <h2 className="text-lg font-semibold">{isLogin ? "Log in" : "Create your account"}</h2>

          <label htmlFor="email" className="mt-5 block text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-brand"
          />

          <label htmlFor="password" className="mt-4 block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={6}
            autoComplete={isLogin ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 outline-none focus:border-brand"
          />

          {error && (
            <p role="alert" className="mt-4 text-sm text-danger">
              {error}
            </p>
          )}
          {info && (
            <p role="status" className="mt-4 text-sm text-ok">
              {info}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="mt-6 w-full rounded-lg bg-brand px-4 py-2.5 font-medium text-brand-ink disabled:opacity-60"
          >
            {busy ? "Please wait…" : isLogin ? "Log in" : "Create account"}
          </button>

          <p className="mt-4 text-sm text-muted">
            {isLogin ? "New here?" : "Already have an account?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(isLogin ? "signup" : "login");
                setError(null);
                setInfo(null);
              }}
              className="font-medium text-brand underline underline-offset-2"
            >
              {isLogin ? "Create an account" : "Log in"}
            </button>
          </p>
        </form>

        <p className="mt-6 text-xs text-muted">
          Nyay AI gives general information about the law. It is not legal advice and does not replace a lawyer.
        </p>
      </div>
    </main>
  );
}
