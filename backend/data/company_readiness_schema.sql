-- Company Readiness results — one row per (run_id, company_key).
-- Run in Supabase SQL editor before enabling persistence.

create table if not exists public.company_readiness_results (
  id                  uuid primary key default gen_random_uuid(),
  run_id              text not null,
  user_id             uuid not null references auth.users (id) on delete cascade,
  created_at          timestamptz default now(),

  company_key         text not null,
  company_display     text,
  readiness_score     int not null,
  readiness_label     text,
  dimensions_passing  int,
  dimensions_total    int,
  dimensions_json     jsonb,
  target_ctc_min      int,
  target_ctc_max      int,
  ctc_delta_min       int,

  unique (run_id, company_key)
);

alter table public.company_readiness_results enable row level security;

drop policy if exists "users see own readiness" on public.company_readiness_results;
create policy "users see own readiness"
  on public.company_readiness_results for select
  using (auth.uid() = user_id);

drop policy if exists "service role inserts readiness" on public.company_readiness_results;
create policy "service role inserts readiness"
  on public.company_readiness_results for insert
  with check (true);
