-- HULA Marketing Operations: two-access-level migration
-- Apply after 001_marketing_operations.sql with a migration owner.
-- Before production rollout, set the intended sole owner to Administrator;
-- all historical operational roles are intentionally reduced to Viewer.

begin;

update public.marketing_members
set role = case when role = 'Administrator' then 'Administrator' else 'Viewer' end,
    updated_at = now()
where role not in ('Viewer', 'Administrator');

alter table public.marketing_members
  drop constraint if exists marketing_members_role_check;
alter table public.marketing_members
  add constraint marketing_members_role_check
  check (role in ('Viewer', 'Administrator'));

drop policy if exists operator_tasks_insert on public.marketing_tasks;
create policy operator_tasks_insert on public.marketing_tasks for insert to authenticated
with check (public.hula_current_marketing_role() = 'Administrator' and created_by = auth.uid());

drop policy if exists operator_tasks_update on public.marketing_tasks;
create policy operator_tasks_update on public.marketing_tasks for update to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

drop policy if exists operator_campaigns_write on public.marketing_campaigns;
create policy operator_campaigns_write on public.marketing_campaigns for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

drop policy if exists operator_content_write on public.content_items;
create policy operator_content_write on public.content_items for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

drop policy if exists operator_experiments_write on public.experiments;
create policy operator_experiments_write on public.experiments for all to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (public.hula_current_marketing_role() = 'Administrator');

drop policy if exists member_approval_request on public.approval_requests;
create policy member_approval_request on public.approval_requests for insert to authenticated
with check (public.hula_current_marketing_role() = 'Administrator' and requested_by = auth.uid());

drop policy if exists approver_decide on public.approval_requests;
create policy approver_decide on public.approval_requests for update to authenticated
using (public.hula_current_marketing_role() = 'Administrator')
with check (
  public.hula_current_marketing_role() = 'Administrator'
  and (not second_approval_required or requested_by <> auth.uid())
);

drop policy if exists operator_jobs_insert on public.job_queue;
create policy operator_jobs_insert on public.job_queue for insert to authenticated
with check (public.hula_current_marketing_role() = 'Administrator' and requested_by = auth.uid());

drop policy if exists audit_read_approver_admin on public.audit_log;
create policy audit_read_approver_admin on public.audit_log for select to authenticated
using (public.hula_current_marketing_role() = 'Administrator');

commit;
