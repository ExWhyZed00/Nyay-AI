-- Nyay AI database schema. Run once in Supabase: SQL Editor -> New query -> paste -> Run.
-- Safe to run again (everything uses IF NOT EXISTS).

create extension if not exists vector;

-- 1) Law text chunks (BNS, BNSS, Constitution) -------------------------------
create table if not exists chunks (
  id             bigserial primary key,
  act            text    not null,            -- 'BNS' | 'BNSS' | 'Constitution'
  section_number text,                        -- '103', '21A' ... (null for fallback chunks)
  title          text,                        -- 'Punishment for murder'
  part           integer not null default 1,  -- long sections are split into parts
  content        text    not null,
  page           integer,
  embedding      vector(1536) not null,       -- text-embedding-3-small = 1536 dimensions
  tsv            tsvector generated always as (
                   to_tsvector('english', coalesce(title, '') || ' ' || content)
                 ) stored
);

create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_tsv_idx       on chunks using gin (tsv);
create index if not exists chunks_lookup_idx    on chunks (act, section_number);

-- 2) Chats ---------------------------------------------------------------------
create table if not exists conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null,                   -- Supabase auth user id
  title      text not null default 'New chat',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists conversations_user_idx on conversations (user_id, updated_at desc);

create table if not exists messages (
  id              bigserial primary key,
  conversation_id uuid not null references conversations (id) on delete cascade,
  user_id         uuid not null,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null,
  sources         jsonb not null default '[]'::jsonb,
  verified        boolean,
  created_at      timestamptz not null default now()
);
create index if not exists messages_conversation_idx on messages (conversation_id, id);

-- 3) Privacy: block direct access through Supabase's public API ----------------
-- Only our FastAPI backend (which connects with the database owner role) can read
-- these tables. Browsers talk to FastAPI, never straight to these tables.
alter table chunks        enable row level security;
alter table conversations enable row level security;
alter table messages      enable row level security;
