-- HULA Marketing Operations foundation migration
-- Repeatable on Supabase/Postgres. Run with a migration owner, never from the browser client.

create extension if not exists pgcrypto;

create or replace function public.hula_touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.marketing_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  role text not null check (role in ('Viewer','Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator')),
  active boolean not null default true,
  invited_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function public.hula_current_marketing_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.marketing_members
  where user_id = auth.uid() and active = true
  limit 1
$$;

create or replace function public.hula_is_marketing_member()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(
    select 1 from public.marketing_members
    where user_id = auth.uid() and active = true
  )
$$;

create table if not exists public.marketing_feature_flags (
  key text primary key,
  enabled boolean not null default false,
  description text not null default '',
  risk_level text not null default 'High' check (risk_level in ('Low','Medium','High')),
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);

create table if not exists public.integration_accounts (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  source_account_id text not null,
  account_label text not null default '',
  state text not null default 'Not configured',
  permission_level text not null default '',
  mode text not null default 'read_only' check (mode in ('read_only','disabled')),
  api_version text not null default '',
  credential_owner text not null default '',
  last_successful_sync timestamptz,
  last_attempted_sync timestamptz,
  next_scheduled_sync timestamptz,
  records_imported bigint not null default 0,
  last_error_code text not null default '',
  last_error_safe text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, source_account_id)
);

create table if not exists public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  integration_account_id uuid references public.integration_accounts(id),
  provider text not null,
  sync_type text not null,
  status text not null,
  data_mode text not null check (data_mode in ('demo','fixture','live','partial')),
  window_start timestamptz,
  window_end timestamptz,
  checkpoint text,
  records_received bigint not null default 0,
  records_upserted bigint not null default 0,
  schema_api_version text not null default '',
  error_code text not null default '',
  error_safe text not null default '',
  correlation_id uuid not null default gen_random_uuid(),
  started_at timestamptz not null default now(),
  completed_at timestamptz
);
create index if not exists sync_runs_provider_started_idx on public.sync_runs(provider, started_at desc);

create table if not exists public.job_queue (
  id uuid primary key default gen_random_uuid(),
  job_type text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'Queued',
  requested_by uuid references auth.users(id),
  requested_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  progress_pct integer not null default 0 check (progress_pct between 0 and 100),
  attempt_count integer not null default 0,
  max_retries integer not null default 5,
  idempotency_key text not null unique,
  lease_owner text,
  lease_expires_at timestamptz,
  error_code text not null default '',
  error_safe text not null default '',
  result jsonb not null default '{}'::jsonb
);
create index if not exists job_queue_claim_idx on public.job_queue(status, requested_at) where status in ('Queued','Retry');

create table if not exists public.metric_definitions (
  technical_name text primary key,
  business_name text not null,
  formula text not null,
  source_system text not null,
  source_fields jsonb not null default '[]'::jsonb,
  filters jsonb not null default '{}'::jsonb,
  timezone text not null default 'Asia/Hong_Kong',
  currency text not null default 'HKD',
  attribution_model text not null default 'Not applicable',
  attribution_window text not null default 'Not applicable',
  refresh_cadence text not null,
  owner text not null,
  limitations text not null default '',
  version integer not null default 1,
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists public.reconciliation_results (
  id uuid primary key default gen_random_uuid(),
  metric_name text not null,
  period_start date not null,
  period_end date not null,
  reference_value numeric,
  platform_value numeric,
  absolute_difference numeric,
  percentage_difference numeric,
  tolerance_pct numeric not null,
  likely_reason text not null default '',
  source_formula text not null,
  status text not null,
  reviewer_note text not null default '',
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(metric_name, period_start, period_end)
);

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  rule_id text not null,
  rule_version text not null,
  source_system text not null,
  source_entity text not null,
  data_period tstzrange,
  data_freshness timestamptz,
  severity text not null check (severity in ('Critical','High','Medium','Low','Info')),
  confidence numeric check (confidence between 0 and 1),
  title text not null,
  explanation text not null,
  evidence jsonb not null,
  recommended_action text not null,
  success_measure text not null,
  playbook_id uuid,
  deduplication_key text not null,
  expiry_at timestamptz,
  status text not null default 'Detected',
  data_mode text not null check (data_mode in ('demo','fixture','live','partial')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists signals_active_dedup_idx on public.signals(deduplication_key) where status not in ('Resolved','Expired','Rejected');

create table if not exists public.marketing_tasks (
  id uuid primary key default gen_random_uuid(),
  signal_id uuid references public.signals(id),
  title text not null,
  description text not null,
  problem_type text not null,
  source_system text not null,
  source_entity text not null default '',
  evidence jsonb not null default '{}'::jsonb,
  data_period tstzrange,
  data_freshness timestamptz,
  severity text not null,
  business_impact text not null default '',
  effort text not null default 'Medium',
  confidence numeric,
  recommended_action text not null,
  playbook_steps jsonb not null default '[]'::jsonb,
  success_measure text not null,
  owner_id uuid references auth.users(id),
  reviewer_id uuid references auth.users(id),
  approver_id uuid references auth.users(id),
  due_date date,
  status text not null default 'Detected',
  rejection_reason text not null default '',
  related_entity_type text not null default '',
  related_entity_id uuid,
  data_mode text not null check (data_mode in ('demo','fixture','live','partial')),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  implemented_at timestamptz,
  verification_state text not null default '',
  measurement_dates date[] not null default '{}'
);
create index if not exists marketing_tasks_owner_status_idx on public.marketing_tasks(owner_id, status, due_date);

create table if not exists public.marketing_campaigns (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  objective text not null,
  audience_definition jsonb not null default '{}'::jsonb,
  geography text not null,
  start_date date,
  end_date date,
  budget_hkd numeric,
  products jsonb not null default '[]'::jsonb,
  channels jsonb not null default '[]'::jsonb,
  assets jsonb not null default '[]'::jsonb,
  utm_plan jsonb not null default '{}'::jsonb,
  status text not null default 'Draft',
  owner_id uuid references auth.users(id),
  source_trend_id text,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.content_items (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid references public.marketing_campaigns(id),
  title text not null,
  content_type text not null,
  business_objective text not null default '',
  audience text not null default '',
  primary_keyword text not null default '',
  search_intent text not null default '',
  related_products jsonb not null default '[]'::jsonb,
  source_evidence jsonb not null default '[]'::jsonb,
  body text not null default '',
  status text not null default 'Idea',
  owner_id uuid references auth.users(id),
  due_date date,
  ai_draft boolean not null default false,
  ai_provenance jsonb not null default '{}'::jsonb,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.approval_requests (
  id uuid primary key default gen_random_uuid(),
  object_type text not null,
  object_id uuid not null,
  summary text not null,
  risk_level text not null check (risk_level in ('Low','Medium','High')),
  requested_by uuid not null references auth.users(id),
  requested_at timestamptz not null default now(),
  status text not null default 'Pending',
  decided_by uuid references auth.users(id),
  decided_at timestamptz,
  decision_comment text not null default '',
  second_approval_required boolean not null default false,
  before_snapshot jsonb not null default '{}'::jsonb,
  proposed_diff jsonb not null default '{}'::jsonb
);
create index if not exists approval_requests_pending_idx on public.approval_requests(status, requested_at) where status = 'Pending';

create table if not exists public.experiments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  hypothesis text not null,
  affected_entity text not null,
  baseline_metric text not null,
  target_metric text not null,
  start_date date,
  end_date date,
  audience text not null default '',
  control_description text not null,
  variant_description text not null,
  confidence_limitation text not null,
  status text not null default 'Proposed',
  result jsonb not null default '{}'::jsonb,
  decision text not null default '',
  owner_id uuid references auth.users(id),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references auth.users(id),
  actor_role text not null,
  action text not null,
  entity_type text not null,
  entity_id text not null,
  detail jsonb not null default '{}'::jsonb,
  correlation_id uuid,
  created_at timestamptz not null default now()
);
create index if not exists audit_log_entity_idx on public.audit_log(entity_type, entity_id, created_at desc);

drop trigger if exists marketing_members_touch on public.marketing_members;
create trigger marketing_members_touch before update on public.marketing_members for each row execute function public.hula_touch_updated_at();
drop trigger if exists integration_accounts_touch on public.integration_accounts;
create trigger integration_accounts_touch before update on public.integration_accounts for each row execute function public.hula_touch_updated_at();
drop trigger if exists signals_touch on public.signals;
create trigger signals_touch before update on public.signals for each row execute function public.hula_touch_updated_at();
drop trigger if exists marketing_tasks_touch on public.marketing_tasks;
create trigger marketing_tasks_touch before update on public.marketing_tasks for each row execute function public.hula_touch_updated_at();
drop trigger if exists marketing_campaigns_touch on public.marketing_campaigns;
create trigger marketing_campaigns_touch before update on public.marketing_campaigns for each row execute function public.hula_touch_updated_at();
drop trigger if exists content_items_touch on public.content_items;
create trigger content_items_touch before update on public.content_items for each row execute function public.hula_touch_updated_at();
drop trigger if exists experiments_touch on public.experiments;
create trigger experiments_touch before update on public.experiments for each row execute function public.hula_touch_updated_at();

alter table public.marketing_members enable row level security;
alter table public.marketing_feature_flags enable row level security;
alter table public.integration_accounts enable row level security;
alter table public.sync_runs enable row level security;
alter table public.job_queue enable row level security;
alter table public.metric_definitions enable row level security;
alter table public.reconciliation_results enable row level security;
alter table public.signals enable row level security;
alter table public.marketing_tasks enable row level security;
alter table public.marketing_campaigns enable row level security;
alter table public.content_items enable row level security;
alter table public.approval_requests enable row level security;
alter table public.experiments enable row level security;
alter table public.audit_log enable row level security;

drop policy if exists members_read_self_or_admin on public.marketing_members;
create policy members_read_self_or_admin on public.marketing_members for select to authenticated
using (user_id = auth.uid() or public.hula_current_marketing_role() = 'Administrator');
drop policy if exists members_admin_write on public.marketing_members;
create policy members_admin_write on public.marketing_members for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

-- All active members may read operational records. Service-role workers bypass
-- RLS server-side; user mutations receive narrower role policies below.
do $$
declare table_name text;
begin
  foreach table_name in array array[
    'marketing_feature_flags','integration_accounts','sync_runs','job_queue',
    'metric_definitions','reconciliation_results','signals','marketing_tasks',
    'marketing_campaigns','content_items','approval_requests','experiments'
  ] loop
    execute format('drop policy if exists member_read on public.%I', table_name);
    execute format('create policy member_read on public.%I for select to authenticated using (public.hula_is_marketing_member())', table_name);
  end loop;
end $$;

drop policy if exists operator_tasks_insert on public.marketing_tasks;
create policy operator_tasks_insert on public.marketing_tasks for insert to authenticated
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator') and created_by = auth.uid());
drop policy if exists operator_tasks_update on public.marketing_tasks;
create policy operator_tasks_update on public.marketing_tasks for update to authenticated
using (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'))
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'));

drop policy if exists operator_campaigns_write on public.marketing_campaigns;
create policy operator_campaigns_write on public.marketing_campaigns for all to authenticated
using (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'))
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'));
drop policy if exists operator_content_write on public.content_items;
create policy operator_content_write on public.content_items for all to authenticated
using (public.hula_current_marketing_role() in ('Marketing Operator','Approver / Manager','Administrator'))
with check (public.hula_current_marketing_role() in ('Marketing Operator','Approver / Manager','Administrator'));
drop policy if exists operator_experiments_write on public.experiments;
create policy operator_experiments_write on public.experiments for all to authenticated
using (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'))
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator'));

drop policy if exists member_approval_request on public.approval_requests;
create policy member_approval_request on public.approval_requests for insert to authenticated
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator') and requested_by = auth.uid());
drop policy if exists approver_decide on public.approval_requests;
create policy approver_decide on public.approval_requests for update to authenticated
using (public.hula_current_marketing_role() in ('Approver / Manager','Administrator'))
with check (
  public.hula_current_marketing_role() in ('Approver / Manager','Administrator')
  and (not second_approval_required or requested_by <> auth.uid())
);

drop policy if exists operator_jobs_insert on public.job_queue;
create policy operator_jobs_insert on public.job_queue for insert to authenticated
with check (public.hula_current_marketing_role() in ('Marketing Operator','Paid Media Specialist','Approver / Manager','Administrator') and requested_by = auth.uid());

drop policy if exists admin_flags_write on public.marketing_feature_flags;
create policy admin_flags_write on public.marketing_feature_flags for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');
drop policy if exists admin_integrations_write on public.integration_accounts;
create policy admin_integrations_write on public.integration_accounts for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');
drop policy if exists admin_metric_write on public.metric_definitions;
create policy admin_metric_write on public.metric_definitions for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

drop policy if exists audit_read_approver_admin on public.audit_log;
create policy audit_read_approver_admin on public.audit_log for select to authenticated
using (public.hula_current_marketing_role() in ('Approver / Manager','Administrator'));
drop policy if exists audit_insert_member on public.audit_log;
create policy audit_insert_member on public.audit_log for insert to authenticated
with check (public.hula_is_marketing_member() and actor_id = auth.uid());
-- No UPDATE or DELETE policy exists for audit_log.

insert into public.marketing_feature_flags(key, enabled, description, risk_level)
values
  ('ENABLE_SHOPIFY_WRITES', false, 'Permit governed Shopify write adapter', 'High'),
  ('ENABLE_GOOGLE_ADS_WRITES', false, 'Permit governed Google Ads write adapter', 'High'),
  ('ENABLE_META_ADS_WRITES', false, 'Permit governed Meta Ads write adapter', 'High'),
  ('ENABLE_KLAVIYO_WRITES', false, 'Permit governed Klaviyo draft adapter', 'High'),
  ('ENABLE_GBP_WRITES', false, 'Permit approved public review reply', 'High'),
  ('ENABLE_MERCHANT_WRITES', false, 'Permit governed Merchant write adapter', 'High'),
  ('ENABLE_AUTOMATIC_PUBLISHING', false, 'Automatic publication is forbidden in first release', 'High'),
  ('ENABLE_AUTOMATIC_BUDGET_CHANGES', false, 'Automatic budget changes are forbidden in first release', 'High')
on conflict (key) do nothing;
