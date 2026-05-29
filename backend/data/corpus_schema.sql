-- RIP V2 corpus tables: resumes, job_descriptions, analysis_runs, patches.
-- Run in Supabase SQL editor before enabling corpus persistence.

create table if not exists public.resumes (
  resume_id           uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users (id) on delete cascade,
  storage_path        text not null,
  parsed_sections     jsonb not null default '{}'::jsonb,
  raw_text_clean      text not null,
  inferred_seniority  text,
  years_of_experience numeric,
  word_count          int,
  skills_mentioned    text[],
  companies_worked_at text[],
  highest_education   text,
  created_at          timestamptz not null default now(),
  is_deleted          boolean not null default false
);

create index if not exists resumes_user_created_idx
  on public.resumes (user_id, created_at desc);

create table if not exists public.job_descriptions (
  jd_id                 uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users (id) on delete cascade,
  target_company        text not null,
  target_role           text not null,
  jd_source             text not null,
  source_url            text,
  jd_intelligence       jsonb not null default '{}'::jsonb,
  raw_text              text not null,
  jd_seniority_level    int,
  min_years_required    int,
  required_skills       text[],
  preferred_skills      text[],
  content_hash          text,
  created_at            timestamptz not null default now()
);

create index if not exists job_descriptions_user_created_idx
  on public.job_descriptions (user_id, created_at desc);

create index if not exists job_descriptions_content_hash_idx
  on public.job_descriptions (content_hash);

create table if not exists public.analysis_runs (
  run_id                uuid primary key,
  user_id               uuid not null references auth.users (id) on delete cascade,
  resume_id             uuid not null references public.resumes (resume_id),
  jd_id                 uuid references public.job_descriptions (jd_id),
  ats_result            jsonb,
  role_fit_result       jsonb,
  gap_analysis_result   jsonb,
  rewrite_result        jsonb,
  patch_result          jsonb,
  positioning_result    jsonb,
  percentile_result     jsonb,
  jd_intelligence       jsonb,
  ats_score             numeric,
  role_fit_band         text,
  percentile            numeric,
  gap_count             int,
  surface_gap_count     int,
  structural_gap_count  int,
  evidence_gap_count    int,
  model_used            text default 'gpt-4o-mini',
  run_duration_ms       int,
  early_exit            boolean not null default false,
  created_at            timestamptz not null default now()
);

create index if not exists analysis_runs_user_created_idx
  on public.analysis_runs (user_id, created_at desc);

create index if not exists analysis_runs_resume_idx
  on public.analysis_runs (resume_id);

create index if not exists analysis_runs_jd_idx
  on public.analysis_runs (jd_id);

create table if not exists public.patches (
  patch_id        uuid primary key default gen_random_uuid(),
  run_id          uuid not null references public.analysis_runs (run_id) on delete cascade,
  user_id         uuid not null references auth.users (id),
  source_patch_id text not null,
  entry_label     text not null,
  gap_type        text not null,
  gap_skill       text,
  original_text   text not null,
  patched_text    text not null,
  style_used      text,
  user_accepted   boolean,
  user_edited     boolean not null default false,
  final_text      text,
  created_at      timestamptz not null default now(),
  decided_at      timestamptz,
  unique (run_id, source_patch_id)
);

create index if not exists patches_run_idx
  on public.patches (run_id);

alter table public.resumes enable row level security;
alter table public.job_descriptions enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.patches enable row level security;

create policy if not exists "users see own resumes"
  on public.resumes
  for select
  using (auth.uid() = user_id);

create policy if not exists "users see own jds"
  on public.job_descriptions
  for select
  using (auth.uid() = user_id);

create policy if not exists "users see own runs"
  on public.analysis_runs
  for select
  using (auth.uid() = user_id);

create policy if not exists "users see own patches"
  on public.patches
  for select
  using (auth.uid() = user_id);
