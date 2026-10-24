# Nyay AI

Ask questions about the **BNS**, the **BNSS** and the **Constitution of India** in English or 8 regional languages
(Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Kannada, Malayalam). Every answer cites the exact sections it used.
Users log in, and their chats are private.

```
Browser (Next.js on Vercel)  --login-->  Supabase Auth
        |  question + login token
        v
FastAPI backend (Render)  -->  LangGraph agent  -->  OpenAI (chat + embeddings)
        |
        v
Supabase Postgres + pgvector  (law text, chats, messages)
```

## How one question flows through the agent

1. **Analyze**: is it a legal question? Which language? Rewrite it as a standalone English search query.
   (Off-topic or greetings get a short polite reply, no search.)
2. **Retrieve (hybrid)**: three searches merged with Reciprocal Rank Fusion:
   exact section lookup ("Section 103 BNS", "Article 21"), semantic search (embeddings + pgvector),
   keyword search (Postgres full-text).
3. **Grade** (Corrective RAG): keep only excerpts that really help. If none do, rewrite the query and search once more,
   then honestly say nothing was found.
4. **Generate**: answer in the user's language using only the excerpts, with `[1]` style citations. Tokens stream live.
5. **Verify** (Self-RAG): check every claim is supported. If not, regenerate once. The UI shows a verified / not verified note.

## What you need installed

| Tool | Version | Check with |
|---|---|---|
| Python | 3.11 or newer (tested on 3.12) | `python --version` |
| Node.js | 22 LTS (20.9+ works) | `node --version` |
| Git | any | `git --version` |

Accounts (all have free tiers): OpenAI (you have a key), Supabase, Render, Vercel, GitHub.

## Step 1: Supabase (database + login)

1. supabase.com -> New project. Save the **database password** you choose.
2. **SQL Editor** -> New query -> paste all of `backend/sql/schema.sql` -> Run. You should see "Success".
3. **Project Settings -> API**: copy the **Project URL** and the **anon / publishable key**.
4. Click **Connect** at the top of the dashboard -> choose **Session pooler** -> copy that connection string.
   Put your password in place of `[YOUR-PASSWORD]`. If the password contains `@ # / :` replace them with
   `%40 %23 %2F %3A`. (Use the *session pooler*, not "Direct connection": direct is IPv6 only and fails on Render.)
5. **Authentication -> Sign In / Providers -> Email**: by default new users must confirm their email.
   For quick local testing you may turn "Confirm email" off. Turn it back on for a public launch.

## Step 2: Backend

Open a terminal in the `backend` folder.

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# open .env and fill in the values
python -m app.check_setup   # every line should say [ OK ]
```

### Load the law text

Download the official **text** PDFs (English) of the three documents and save them in `backend/data/`
(for example from India Code, indiacode.nic.in, or the Legislative Department, legislative.gov.in).
Scanned image PDFs will not work.

```bash
# 1) Look first. Nothing is saved and nothing is charged.
python -m app.ingestion.ingest --act BNS --file data/bns.pdf --dry-run
# 2) If the section count looks right, load it
python -m app.ingestion.ingest --act BNS --file data/bns.pdf
python -m app.ingestion.ingest --act BNSS --file data/bnss.pdf
python -m app.ingestion.ingest --act Constitution --file data/constitution.pdf
```

Expected counts in the dry run: BNS about 358, BNSS about 531, Constitution roughly 395 to 470 articles.
If the count is far off, or it says `Mode: fallback`, the PDF layout is unusual: send me the dry-run output.
Search still works in fallback mode, but exact "Section 103" lookup does not.
Running ingestion again for the same act replaces its old data.

### Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/health. It should show `{"status":"ok"}`.

## Step 3: Frontend

Open a second terminal in the `frontend` folder.

```bash
npm install
cp .env.local.example .env.local     # Windows: copy .env.local.example .env.local
# fill in the 3 values, then:
npm run dev
```

Open http://localhost:3000, create an account, log in, and ask a question.

## Step 4: Deploy for free

Push the whole project to a GitHub repository first (`.env` files are git-ignored, never upload them).

**Backend on Render**
1. Render -> New -> Web Service -> pick your repo.
2. Language/Runtime **Docker**, **Root Directory** `backend`, Instance type **Free**.
3. Environment variables: `OPENAI_API_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `OPENAI_CHAT_MODEL` and `FRONTEND_ORIGINS` (put your Vercel URL here after step below, no trailing slash).
4. Health check path: `/health`. Deploy. Copy your `https://....onrender.com` URL.

**Frontend on Vercel**
1. Vercel -> Add New -> Project -> pick your repo, **Root Directory** `frontend`.
2. Environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
   `NEXT_PUBLIC_API_URL` (your Render URL, no trailing slash). Deploy.

**Then connect them**
- Render: set `FRONTEND_ORIGINS` to your Vercel URL and redeploy.
- Supabase -> Authentication -> URL Configuration: set **Site URL** to your Vercel URL
  (so email confirmation links open your site, not localhost).

## Things to know about free hosting (check current limits, they change)

- **Render free services go to sleep when idle.** The first question after a pause can take up to about a minute.
  The chat screen tells the user why.
- **Supabase free projects can pause after a period of inactivity.** Open the dashboard and restore it if that happens.
- **OpenAI is pay-as-you-go.** Each question makes several model calls (analyze, grade, answer, verify).
  Set a monthly spending limit in the OpenAI dashboard. The API limits each user to 20 questions per 10 minutes.
- **Model retirement.** `gpt-4o-mini` is the default because it is fast and supports temperature 0. Reports say OpenAI
  retires the GPT-4o family from the API on 14 January 2027. Before then, change `OPENAI_CHAT_MODEL` to a newer small
  model such as `gpt-5-mini` and set `OPENAI_TEMPERATURE=default` (reasoning models reject temperature 0).
  Optional: `OPENAI_REASONING_EFFORT=low` for speed. Run `python -m app.check_setup` after changing it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `check_setup`: database failed | Wrong `DATABASE_URL`. Use the Session pooler string, real password, special characters encoded. |
| `Tables missing` | Run `backend/sql/schema.sql` in the Supabase SQL editor. |
| Browser shows "Could not reach the server" | Backend not running, wrong `NEXT_PUBLIC_API_URL`, or `FRONTEND_ORIGINS` does not contain your site's exact URL. |
| Login works but chat says "Session expired" | `SUPABASE_URL` / `SUPABASE_ANON_KEY` in the backend `.env` do not match the frontend's. |
| "Email not confirmed" | Click the link in the confirmation email, or turn off "Confirm email" while testing. |
| Answers say nothing was found | Law data not loaded (`check_setup` lists row counts), or the question is outside BNS/BNSS/Constitution. |
| OpenAI error about `temperature` | You switched to a reasoning model: set `OPENAI_TEMPERATURE=default`. |

## Project layout

```
backend/
  app/main.py            API: /chat (streaming), /conversations, /health
  app/auth.py            login check (asks Supabase who owns the token) + rate limit
  app/graph/             the agent: nodes.py, prompts.py, builder.py, state.py
  app/retrieval.py       exact + semantic + keyword search, RRF merge
  app/ingestion/         PDF -> chunks -> embeddings -> database
  app/check_setup.py     first-run checker
  sql/schema.sql         database tables (run once in Supabase)
  tests/                 34 automated tests (pytest)
frontend/
  src/app/               login page and chat page
  src/components/        sidebar, message view (citations), composer
  src/lib/               API client (streaming), Supabase client, types
```

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```
The API tests need a Postgres with `schema.sql` applied. Point `TEST_DATABASE_URL` at a throwaway database
(never your real Supabase one). Without it, those tests are skipped or fail to connect.

## Privacy and safety notes

- Chats are stored per user. Every query filters by the logged-in user's id, and the tables are closed to Supabase's
  public API (row level security with no public policies), so only this backend can read them.
- The assistant answers only from the three loaded texts and says so when it cannot find something.
  The interface always shows that this is general information and not legal advice.
- Quality in smaller languages varies. Have native speakers test a few questions per language before you publicise it.
