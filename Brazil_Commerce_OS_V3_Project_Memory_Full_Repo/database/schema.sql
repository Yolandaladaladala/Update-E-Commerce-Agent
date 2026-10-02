-- Brazil Commerce OS - Project Memory schema
-- Run this entire file once in Supabase > SQL Editor.
-- It creates private per-user project memory, run history, file metadata, reports,
-- evidence, creator records, campaigns, finance metrics, and a private Storage bucket.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_name text not null,
  product_name text not null default '',
  category text not null default '',
  target_market text not null default 'Brazil',
  selected_platform text not null default '',
  current_stage text not null default 'market' check (current_stage in ('market','operations','marketing','finance')),
  status text not null default 'active' check (status in ('active','paused','completed','archived')),
  notes text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists projects_user_updated_idx on public.projects(user_id, updated_at desc);

drop trigger if exists trg_projects_updated_at on public.projects;
create trigger trg_projects_updated_at before update on public.projects
for each row execute function public.set_updated_at();

create table if not exists public.project_modules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  module text not null check (module in ('market','operations','marketing','finance')),
  status text not null default 'not_started' check (status in ('not_started','in_progress','completed','blocked','waiting_for_data')),
  progress_percent integer not null default 0 check (progress_percent between 0 and 100),
  blocking_count integer not null default 0 check (blocking_count >= 0),
  missing_count integer not null default 0 check (missing_count >= 0),
  latest_run_id uuid,
  updated_at timestamptz not null default now(),
  unique(project_id, module)
);
create index if not exists project_modules_project_idx on public.project_modules(project_id);

create table if not exists public.module_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  module text not null check (module in ('market','operations','marketing','finance')),
  version integer not null default 1 check (version > 0),
  status text not null default 'completed',
  input_snapshot jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(project_id, module, version)
);
create index if not exists module_runs_project_module_idx on public.module_runs(project_id, module, version desc);

alter table public.project_modules
  drop constraint if exists project_modules_latest_run_id_fkey;
alter table public.project_modules
  add constraint project_modules_latest_run_id_fkey
  foreign key (latest_run_id) references public.module_runs(id) on delete set null;

create table if not exists public.project_files (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  module text not null default 'project',
  file_name text not null,
  storage_path text not null unique,
  mime_type text not null default 'application/octet-stream',
  size_bytes bigint not null default 0,
  source_kind text not null default 'upload',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists project_files_project_idx on public.project_files(project_id, created_at desc);

create table if not exists public.reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  module text not null,
  report_type text not null,
  version integer not null default 1,
  file_id uuid references public.project_files(id) on delete set null,
  storage_path text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists reports_project_idx on public.reports(project_id, module, created_at desc);

create table if not exists public.market_evidence (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid references public.module_runs(id) on delete cascade,
  source_id text,
  title text,
  url text,
  source_type text,
  geography text,
  published_date text,
  snippet text,
  metadata jsonb not null default '{}'::jsonb,
  retrieved_at timestamptz not null default now()
);
create index if not exists market_evidence_project_idx on public.market_evidence(project_id, retrieved_at desc);

create table if not exists public.creator_records (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  source_file_id uuid references public.project_files(id) on delete set null,
  creator_key text not null,
  display_name text,
  handle text,
  platform text,
  category text,
  followers numeric,
  avg_views numeric,
  engagement_rate numeric,
  fee_brl numeric,
  contact text,
  profile_url text,
  source_url text,
  fit_score numeric,
  raw_data jsonb not null default '{}'::jsonb,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(project_id, creator_key)
);
create index if not exists creator_records_project_idx on public.creator_records(project_id);

drop trigger if exists trg_creator_records_updated_at on public.creator_records;
create trigger trg_creator_records_updated_at before update on public.creator_records
for each row execute function public.set_updated_at();

create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  campaign_name text not null,
  objective text,
  platform text,
  budget_brl numeric,
  status text not null default 'planning',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists trg_campaigns_updated_at on public.campaigns;
create trigger trg_campaigns_updated_at before update on public.campaigns
for each row execute function public.set_updated_at();

create table if not exists public.finance_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  run_id uuid references public.module_runs(id) on delete cascade,
  metric_name text not null,
  metric_value numeric,
  metric_text text,
  unit text,
  dimension jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists finance_metrics_project_idx on public.finance_metrics(project_id, metric_name);

create table if not exists public.activity_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid not null references public.projects(id) on delete cascade,
  module text not null default 'project',
  action text not null,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists activity_log_project_idx on public.activity_log(project_id, created_at desc);

-- -------------------------
-- Row Level Security
-- -------------------------
alter table public.projects enable row level security;
alter table public.project_modules enable row level security;
alter table public.module_runs enable row level security;
alter table public.project_files enable row level security;
alter table public.reports enable row level security;
alter table public.market_evidence enable row level security;
alter table public.creator_records enable row level security;
alter table public.campaigns enable row level security;
alter table public.finance_metrics enable row level security;
alter table public.activity_log enable row level security;

-- Recreate simple owner policies. Each table stores user_id explicitly.
do $$
declare
  tbl text;
begin
  foreach tbl in array array[
    'projects','project_modules','module_runs','project_files','reports',
    'market_evidence','creator_records','campaigns','finance_metrics','activity_log'
  ]
  loop
    execute format('drop policy if exists "owner_select" on public.%I', tbl);
    execute format('drop policy if exists "owner_insert" on public.%I', tbl);
    execute format('drop policy if exists "owner_update" on public.%I', tbl);
    execute format('drop policy if exists "owner_delete" on public.%I', tbl);
    execute format('create policy "owner_select" on public.%I for select using (auth.uid() = user_id)', tbl);
    execute format('create policy "owner_insert" on public.%I for insert with check (auth.uid() = user_id)', tbl);
    execute format('create policy "owner_update" on public.%I for update using (auth.uid() = user_id) with check (auth.uid() = user_id)', tbl);
    execute format('create policy "owner_delete" on public.%I for delete using (auth.uid() = user_id)', tbl);
  end loop;
end $$;

-- -------------------------
-- Private file bucket
-- -------------------------
insert into storage.buckets (id, name, public)
values ('bcos-project-files', 'bcos-project-files', false)
on conflict (id) do update set public = false;

-- Paths are always: <auth.uid()>/<project_id>/<module>/<file>
drop policy if exists "bcos_files_select" on storage.objects;
drop policy if exists "bcos_files_insert" on storage.objects;
drop policy if exists "bcos_files_update" on storage.objects;
drop policy if exists "bcos_files_delete" on storage.objects;

create policy "bcos_files_select" on storage.objects
for select to authenticated
using (
  bucket_id = 'bcos-project-files'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bcos_files_insert" on storage.objects
for insert to authenticated
with check (
  bucket_id = 'bcos-project-files'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bcos_files_update" on storage.objects
for update to authenticated
using (
  bucket_id = 'bcos-project-files'
  and (storage.foldername(name))[1] = auth.uid()::text
)
with check (
  bucket_id = 'bcos-project-files'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bcos_files_delete" on storage.objects
for delete to authenticated
using (
  bucket_id = 'bcos-project-files'
  and (storage.foldername(name))[1] = auth.uid()::text
);
