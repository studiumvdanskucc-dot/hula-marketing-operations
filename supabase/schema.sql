-- Run this once in Supabase → SQL Editor.
-- The Streamlit server uses SUPABASE_SECRET_KEY; no client-side access is needed.

create extension if not exists pgcrypto;

create table if not exists public.hula_trend_snapshots (
    id uuid primary key default gen_random_uuid(),
    week_start date not null unique,
    generated_at timestamptz not null,
    mode text not null,
    source_status jsonb not null default '{}'::jsonb,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists hula_trend_snapshots_generated_at_idx
    on public.hula_trend_snapshots (generated_at desc);

create table if not exists public.hula_blog_drafts (
    id uuid primary key default gen_random_uuid(),
    generated_at timestamptz not null,
    trend_id text not null,
    reason text not null default '',
    title text not null,
    draft jsonb not null,
    created_at timestamptz not null default now()
);

create index if not exists hula_blog_drafts_generated_at_idx
    on public.hula_blog_drafts (generated_at desc);

alter table public.hula_trend_snapshots enable row level security;
alter table public.hula_blog_drafts enable row level security;

revoke all on public.hula_trend_snapshots from anon, authenticated;
revoke all on public.hula_blog_drafts from anon, authenticated;
grant select, insert, update, delete on public.hula_trend_snapshots to service_role;
grant select, insert, update, delete on public.hula_blog_drafts to service_role;
