-- Supabase schema for mock interview session persistence.
-- Run in Supabase SQL editor before enabling DB-backed interview history.

create table if not exists public.interview_sessions (
  session_id     text primary key,
  user_id        uuid not null references auth.users (id) on delete cascade,
  company        text not null,
  seniority      text not null,
  question_mode  text not null,
  questions      jsonb not null default '[]'::jsonb,
  answers        jsonb not null default '[]'::jsonb,
  feedback       jsonb not null default '[]'::jsonb,
  summary        jsonb,
  model_answers  jsonb,
  created_at     timestamptz not null default now(),
  completed_at   timestamptz
);

create index if not exists interview_sessions_user_created_idx
  on public.interview_sessions (user_id, created_at desc);

alter table public.interview_sessions enable row level security;

-- Service role (backend) bypasses RLS; optional user-scoped policy for direct client reads:
create policy if not exists "Users read own interview sessions"
  on public.interview_sessions
  for select
  using (auth.uid() = user_id);
