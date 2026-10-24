"""First-run checker. Run from the backend folder:  python -m app.check_setup"""
import sys

OK, BAD = "[ OK ]", "[FAIL]"
failed = False


def report(ok: bool, text: str) -> None:
    global failed
    failed = failed or not ok
    print(f"{OK if ok else BAD} {text}")


def main() -> int:
    # 1. settings
    try:
        from app.config import ENV_FILE, get_settings

        s = get_settings()
        report(True, f"Settings loaded (.env at {ENV_FILE})")
    except Exception as e:  # noqa: BLE001
        print(f"{BAD} Settings problem. Is backend/.env filled in?\n{e}")
        return 1

    # 2. database
    try:
        import psycopg

        with psycopg.connect(s.database_url, prepare_threshold=None, connect_timeout=15) as conn:
            conn.execute("select 1")
            has_vec = conn.execute("select 1 from pg_extension where extname = 'vector'").fetchone()
            report(True, "Database connection works")
            report(bool(has_vec), "pgvector extension is enabled" if has_vec else "pgvector missing: run sql/schema.sql")
            tables = {r[0] for r in conn.execute("select tablename from pg_tables where schemaname = 'public'").fetchall()}
            missing = {"chunks", "conversations", "messages"} - tables
            report(not missing, "Tables exist" if not missing else f"Tables missing {sorted(missing)}: run sql/schema.sql")
            if "chunks" in tables:
                rows = conn.execute("select act, count(*) from chunks group by act order by act").fetchall()
                if rows:
                    report(True, "Law data loaded: " + ", ".join(f"{a}={n}" for a, n in rows))
                else:
                    print("[INFO] No law data yet. Next: python -m app.ingestion.ingest --act BNS --file data/bns.pdf")
    except Exception as e:  # noqa: BLE001
        report(False, f"Database connection failed: {e}")

    # 3. OpenAI
    try:
        from app.clients import embed_query, get_llm
        from app.config import EMBEDDING_DIM

        vec = embed_query("test")
        report(len(vec) == EMBEDDING_DIM, f"OpenAI embeddings work ({len(vec)} dimensions)")
        out = get_llm().invoke("Reply with the single word: OK")
        report(True, f"OpenAI chat model '{s.openai_chat_model}' works (replied: {str(out.content)[:20]!r})")
    except Exception as e:  # noqa: BLE001
        report(False, f"OpenAI problem: {e}")

    # 4. Supabase auth
    try:
        import httpx

        r = httpx.get(f"{s.supabase_url}/auth/v1/settings", headers={"apikey": s.supabase_anon_key}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            report(True, "Supabase URL and key are accepted")
            if data.get("mailer_autoconfirm") is False:
                print("[INFO] Email confirmation is ON: new users must click the email link before logging in.")
            if data.get("disable_signup"):
                report(False, "Sign-ups are disabled in Supabase (Authentication > Sign In / Providers)")
        else:
            report(False, f"Supabase answered {r.status_code}: check SUPABASE_URL and SUPABASE_ANON_KEY")
    except Exception as e:  # noqa: BLE001
        report(False, f"Supabase unreachable: {e}")

    print("\nAll good." if not failed else "\nFix the [FAIL] lines above, then run this again.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
