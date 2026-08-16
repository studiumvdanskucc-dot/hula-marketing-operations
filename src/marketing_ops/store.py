from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .models import (
    ApprovalStatus,
    Permission,
    RiskLevel,
    Role,
    Signal,
    TaskStatus,
    UserIdentity,
    utc_now,
)
from .permissions import require_permission
from .security import redact_mapping


SCHEMA = """
pragma foreign_keys = on;

create table if not exists tasks (
    id text primary key,
    title text not null,
    description text not null,
    problem_type text not null,
    source_system text not null,
    source_entity text not null default '',
    evidence_json text not null default '{}',
    data_period text not null default '',
    data_freshness text not null default '',
    severity text not null,
    business_impact text not null default '',
    effort text not null default 'Medium',
    confidence real,
    recommended_action text not null default '',
    playbook_json text not null default '[]',
    success_measure text not null default '',
    owner text not null default '',
    reviewer text not null default '',
    approver text not null default '',
    due_date text,
    status text not null,
    rejection_reason text not null default '',
    related_entity_type text not null default '',
    related_entity_id text not null default '',
    deduplication_key text not null default '',
    data_mode text not null default 'demo',
    created_by text not null,
    created_at text not null,
    updated_at text not null,
    implemented_at text,
    verification_state text not null default '',
    measurement_dates_json text not null default '[]'
);
create unique index if not exists tasks_active_dedup_idx
    on tasks(deduplication_key)
    where deduplication_key <> '' and status not in ('Completed','Cancelled','Rejected');
create index if not exists tasks_status_due_idx on tasks(status, due_date);

create table if not exists approvals (
    id text primary key,
    object_type text not null,
    object_id text not null,
    summary text not null,
    risk_level text not null,
    requested_by text not null,
    requested_by_name text not null,
    requested_at text not null,
    status text not null,
    decided_by text,
    decided_by_name text,
    decided_at text,
    decision_comment text not null default '',
    second_approval_required integer not null default 0,
    before_snapshot_json text not null default '{}',
    proposed_diff_json text not null default '{}'
);
create index if not exists approvals_status_idx on approvals(status, requested_at);

create table if not exists marketing_campaigns (
    id text primary key,
    name text not null,
    objective text not null,
    audience text not null,
    geography text not null,
    start_date text,
    end_date text,
    budget_hkd real,
    products text not null default '',
    channels_json text not null default '[]',
    status text not null default 'Draft',
    owner text not null,
    source_trend text not null default '',
    utm_plan text not null default '',
    created_by text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists content_items (
    id text primary key,
    title text not null,
    content_type text not null,
    business_objective text not null default '',
    audience text not null default '',
    primary_keyword text not null default '',
    search_intent text not null default '',
    related_products text not null default '',
    source_evidence_json text not null default '[]',
    body text not null default '',
    status text not null default 'Idea',
    owner text not null,
    due_date text,
    ai_draft integer not null default 0,
    approval_id text,
    created_by text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists experiments (
    id text primary key,
    name text not null,
    hypothesis text not null,
    affected_entity text not null,
    baseline_metric text not null,
    target_metric text not null,
    start_date text,
    end_date text,
    audience text not null default '',
    control_description text not null default '',
    variant_description text not null default '',
    confidence_limitation text not null default '',
    status text not null default 'Proposed',
    result text not null default '',
    decision text not null default '',
    owner text not null,
    created_by text not null,
    created_at text not null,
    updated_at text not null
);

create table if not exists job_queue (
    id text primary key,
    job_type text not null,
    payload_json text not null,
    status text not null,
    requested_by text not null,
    requested_at text not null,
    started_at text,
    completed_at text,
    progress_pct integer not null default 0,
    attempt_count integer not null default 0,
    max_retries integer not null default 5,
    idempotency_key text not null,
    lease_owner text,
    lease_expires_at text,
    error text not null default '',
    result_json text not null default '{}'
);
create unique index if not exists job_idempotency_idx on job_queue(idempotency_key);

create table if not exists audit_log (
    id integer primary key autoincrement,
    actor_id text not null,
    actor_role text not null,
    action text not null,
    entity_type text not null,
    entity_id text not null,
    detail_json text not null,
    created_at text not null
);
create index if not exists audit_entity_idx on audit_log(entity_type, entity_id, created_at);
"""


def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in list(result):
        if key.endswith("_json") and isinstance(result[key], str):
            try:
                result[key.removesuffix("_json")] = json.loads(result[key])
            except json.JSONDecodeError:
                result[key.removesuffix("_json")] = None
            del result[key]
    for key in ("second_approval_required", "ai_draft"):
        if key in result:
            result[key] = bool(result[key])
    return result


class OperationalStore:
    """Small local operational store for demo/offline mode.

    Production deployments use the equivalent Postgres migrations. The local
    store makes every workflow testable without claiming a Supabase connection.
    """

    def __init__(self, path: str | Path, *, seed_demo: bool = False) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if seed_demo:
            self.seed_demo()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("pragma foreign_keys = on")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _audit(
        self,
        connection: sqlite3.Connection,
        actor: UserIdentity,
        action: str,
        entity_type: str,
        entity_id: str,
        detail: dict[str, Any],
    ) -> None:
        safe_detail = redact_mapping(detail)
        connection.execute(
            "insert into audit_log(actor_id,actor_role,action,entity_type,entity_id,detail_json,created_at) values(?,?,?,?,?,?,?)",
            (
                actor.user_id,
                actor.role.value,
                action,
                entity_type,
                entity_id,
                json.dumps(safe_detail, ensure_ascii=False, default=str),
                utc_now(),
            ),
        )

    def seed_demo(self) -> None:
        actor = UserIdentity(
            "demo:system",
            "demo@local.invalid",
            "Demo seed",
            role=Role.ADMINISTRATOR,
            demo=True,
        )
        if not self.list_tasks(limit=1):
            seed_tasks = [
                ("Resolve the store revenue reconciliation gap", "Data quality", "Agency report", "High", "The store rows exceed total revenue by HK$30,146.56.", "Confirm location mapping and excluded orders.", "2026-08-09"),
                ("Rewrite the Preowned vs Preloved search snippet", "SEO opportunity", "Search Console", "High", "31,589 impressions generated only 19 clicks in the reference report.", "Prepare a title/meta draft and route it for review.", "2026-08-14"),
                ("Refresh fatigued Bags retargeting creative", "Paid media", "Meta Ads", "Medium", "Frequency is 4.13 while CTR is 0.59% and purchases are zero in the fixture.", "Ask the paid-media specialist to review a new creative rotation.", "2026-08-10"),
            ]
            for title, problem, source, severity, evidence, action, due in seed_tasks:
                self.create_task(
                    actor,
                    title=title,
                    description=evidence,
                    problem_type=problem,
                    source_system=source,
                    evidence={"summary": evidence, "data_mode": "fixture"},
                    severity=severity,
                    recommended_action=action,
                    due_date=due,
                    owner="Marketing" if source != "Meta Ads" else "Paid media",
                    data_mode="fixture",
                )
        if not self.list_campaigns(limit=1):
            self.create_campaign(
                actor,
                name="Singapore launch — holding plan",
                objective="Acquire qualified Singapore buyers without compromising Hong Kong efficiency",
                audience="Singapore luxury resale shoppers and HULA subscribers",
                geography="Singapore",
                start_date="2026-09-01",
                end_date="2026-09-30",
                budget_hkd=16_500,
                products="Approved available inventory only",
                channels=["Google Ads", "Meta Ads", "Klaviyo", "Landing page"],
                owner="Marketing",
                status="Awaiting decision",
                utm_plan="utm_campaign=sg_launch_2026_09",
            )
        if not self.list_content_items(limit=1):
            self.create_content_item(
                actor,
                title="Preowned vs Preloved — snippet and article refresh",
                content_type="Blog article",
                owner="Marketing",
                business_objective="Increase qualified organic clicks to HULA's educational content and collections",
                audience="Luxury shoppers comparing resale terminology",
                primary_keyword="preowned vs preloved",
                search_intent="Informational / commercial investigation",
                related_products="Available authenticated collections; verify before linking",
                source_evidence=[
                    {
                        "source": "Agency-report fixture",
                        "period": "July 2026",
                        "impressions": 31589,
                        "clicks": 19,
                        "position": 8.9,
                    }
                ],
                body="WORKING DRAFT — FIXTURE\n\nClarify the difference in HULA's own voice, then connect the answer to authentication, circular fashion and currently available inventory. Product and authentication claims require named expert review.",
                status="Brief",
                due_date="2026-08-14",
                ai_draft=True,
            )

    def create_task(
        self,
        actor: UserIdentity,
        *,
        title: str,
        description: str,
        problem_type: str,
        source_system: str,
        evidence: dict[str, Any] | str,
        severity: str,
        recommended_action: str,
        owner: str,
        due_date: str | None = None,
        source_entity: str = "",
        data_period: str = "",
        data_freshness: str = "",
        business_impact: str = "",
        effort: str = "Medium",
        confidence: float | None = None,
        playbook: list[str] | tuple[str, ...] = (),
        success_measure: str = "",
        deduplication_key: str = "",
        data_mode: str = "demo",
        related_entity_type: str = "",
        related_entity_id: str = "",
        status: str = TaskStatus.DETECTED.value,
    ) -> str:
        require_permission(actor.role, Permission.MANAGE_TASKS)
        if data_mode == "demo" and status in {
            TaskStatus.APPROVED.value,
            TaskStatus.SCHEDULED.value,
            TaskStatus.IMPLEMENTED.value,
        }:
            raise ValueError("Demo-derived work cannot be approved, scheduled, or implemented.")
        task_id = str(uuid.uuid4())
        now = utc_now()
        evidence_payload = evidence if isinstance(evidence, dict) else {"summary": evidence}
        with self._connect() as connection:
            try:
                connection.execute(
                    """insert into tasks(
                        id,title,description,problem_type,source_system,source_entity,evidence_json,
                        data_period,data_freshness,severity,business_impact,effort,confidence,
                        recommended_action,playbook_json,success_measure,owner,due_date,status,
                        related_entity_type,related_entity_id,deduplication_key,data_mode,created_by,
                        created_at,updated_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id,
                        title.strip(),
                        description.strip(),
                        problem_type,
                        source_system,
                        source_entity,
                        json.dumps(redact_mapping(evidence_payload), ensure_ascii=False, default=str),
                        data_period,
                        data_freshness,
                        severity,
                        business_impact,
                        effort,
                        confidence,
                        recommended_action,
                        json.dumps(list(playbook), ensure_ascii=False),
                        success_measure,
                        owner,
                        due_date,
                        status,
                        related_entity_type,
                        related_entity_id,
                        deduplication_key,
                        data_mode,
                        actor.user_id,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                if "deduplication_key" in str(exc) or "UNIQUE" in str(exc):
                    existing = connection.execute(
                        "select id from tasks where deduplication_key=? and status not in ('Completed','Cancelled','Rejected')",
                        (deduplication_key,),
                    ).fetchone()
                    if existing:
                        return str(existing["id"])
                raise
            self._audit(connection, actor, "task.created", "task", task_id, {"title": title, "status": status, "data_mode": data_mode})
        return task_id

    def create_task_from_signal(self, actor: UserIdentity, signal: Signal, *, due_date: str | None = None) -> str:
        return self.create_task(
            actor,
            title=signal.title,
            description=signal.description,
            problem_type=signal.rule_id,
            source_system=signal.source_system,
            source_entity=signal.source_entity,
            evidence={"summary": signal.evidence, "rule_version": signal.rule_version, "metadata": signal.metadata},
            data_period=signal.data_period,
            data_freshness=signal.data_freshness,
            severity=signal.severity.value,
            business_impact=signal.why_it_matters,
            confidence=signal.confidence,
            recommended_action=signal.recommended_action,
            playbook=signal.playbook,
            success_measure=signal.success_measure,
            owner=signal.owner_role.value,
            due_date=due_date,
            deduplication_key=signal.deduplication_key,
            data_mode=signal.data_mode.value,
        )

    def list_tasks(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = "select * from tasks"
        params: list[Any] = []
        if status:
            query += " where status=?"
            params.append(status)
        query += " order by case severity when 'Critical' then 1 when 'High' then 2 when 'Medium' then 3 when 'Low' then 4 else 5 end, due_date is null, due_date, created_at desc limit ?"
        params.append(limit)
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute(query, params).fetchall()]

    def update_task_status(self, actor: UserIdentity, task_id: str, status: TaskStatus, *, rejection_reason: str = "") -> None:
        require_permission(actor.role, Permission.MANAGE_TASKS)
        if status is TaskStatus.REJECTED and not rejection_reason.strip():
            raise ValueError("A rejection reason is required.")
        with self._connect() as connection:
            row = connection.execute("select * from tasks where id=?", (task_id,)).fetchone()
            if not row:
                raise KeyError("Task not found.")
            if row["data_mode"] in {"demo", "fixture"} and status in {TaskStatus.APPROVED, TaskStatus.SCHEDULED, TaskStatus.IMPLEMENTED}:
                raise ValueError("Fixture/demo tasks cannot be approved, scheduled, or implemented as live work.")
            implemented_at = utc_now() if status is TaskStatus.IMPLEMENTED else row["implemented_at"]
            connection.execute("update tasks set status=?, rejection_reason=?, implemented_at=?, updated_at=? where id=?", (status.value, rejection_reason.strip(), implemented_at, utc_now(), task_id))
            self._audit(connection, actor, "task.status_changed", "task", task_id, {"from": row["status"], "to": status.value, "rejection_reason": rejection_reason})

    def create_approval(
        self,
        actor: UserIdentity,
        *,
        object_type: str,
        object_id: str,
        summary: str,
        risk_level: RiskLevel,
        before_snapshot: dict[str, Any] | None = None,
        proposed_diff: dict[str, Any] | None = None,
        second_approval_required: bool | None = None,
    ) -> str:
        require_permission(actor.role, Permission.REQUEST_APPROVAL)
        approval_id = str(uuid.uuid4())
        require_second = risk_level is RiskLevel.HIGH if second_approval_required is None else second_approval_required
        with self._connect() as connection:
            connection.execute(
                """insert into approvals(id,object_type,object_id,summary,risk_level,requested_by,requested_by_name,requested_at,status,second_approval_required,before_snapshot_json,proposed_diff_json)
                   values(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (approval_id, object_type, object_id, summary, risk_level.value, actor.user_id, actor.display_name, utc_now(), ApprovalStatus.PENDING.value, int(require_second), json.dumps(redact_mapping(before_snapshot or {}), default=str), json.dumps(redact_mapping(proposed_diff or {}), default=str)),
            )
            self._audit(connection, actor, "approval.requested", "approval", approval_id, {"object_type": object_type, "object_id": object_id, "risk": risk_level.value})
        return approval_id

    def list_approvals(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = "select * from approvals"
        params: list[Any] = []
        if status:
            query += " where status=?"
            params.append(status)
        query += " order by requested_at desc limit ?"
        params.append(limit)
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute(query, params).fetchall()]

    def decide_approval(self, actor: UserIdentity, approval_id: str, decision: ApprovalStatus, comment: str) -> None:
        require_permission(actor.role, Permission.DECIDE_APPROVAL)
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            raise ValueError("Decision must be Approved or Rejected.")
        if not comment.strip():
            raise ValueError("A decision comment is required.")
        with self._connect() as connection:
            row = connection.execute("select * from approvals where id=?", (approval_id,)).fetchone()
            if not row:
                raise KeyError("Approval not found.")
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ValueError("This approval is no longer pending.")
            if row["second_approval_required"] and row["requested_by"] == actor.user_id:
                raise PermissionError("The requester cannot provide the required second approval.")
            connection.execute("update approvals set status=?,decided_by=?,decided_by_name=?,decided_at=?,decision_comment=? where id=?", (decision.value, actor.user_id, actor.display_name, utc_now(), comment.strip(), approval_id))
            self._audit(connection, actor, "approval.decided", "approval", approval_id, {"decision": decision.value, "comment": comment})

    def create_campaign(
        self,
        actor: UserIdentity,
        *,
        name: str,
        objective: str,
        audience: str,
        geography: str,
        owner: str,
        channels: list[str] | tuple[str, ...],
        start_date: str | None = None,
        end_date: str | None = None,
        budget_hkd: float | None = None,
        products: str = "",
        status: str = "Draft",
        source_trend: str = "",
        utm_plan: str = "",
    ) -> str:
        require_permission(actor.role, Permission.MANAGE_CAMPAIGNS)
        campaign_id = str(uuid.uuid4())
        now = utc_now()
        with self._connect() as connection:
            connection.execute("""insert into marketing_campaigns(id,name,objective,audience,geography,start_date,end_date,budget_hkd,products,channels_json,status,owner,source_trend,utm_plan,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (campaign_id, name, objective, audience, geography, start_date, end_date, budget_hkd, products, json.dumps(list(channels)), status, owner, source_trend, utm_plan, actor.user_id, now, now))
            self._audit(connection, actor, "campaign.created", "campaign", campaign_id, {"name": name, "status": status, "channels": list(channels)})
        return campaign_id

    def list_campaigns(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute("select * from marketing_campaigns order by start_date is null,start_date,created_at desc limit ?", (limit,)).fetchall()]

    def create_content_item(
        self,
        actor: UserIdentity,
        *,
        title: str,
        content_type: str,
        owner: str,
        business_objective: str = "",
        audience: str = "",
        primary_keyword: str = "",
        search_intent: str = "",
        related_products: str = "",
        source_evidence: list[dict[str, Any]] | None = None,
        body: str = "",
        status: str = "Idea",
        due_date: str | None = None,
        ai_draft: bool = False,
    ) -> str:
        require_permission(actor.role, Permission.MANAGE_CONTENT)
        content_id = str(uuid.uuid4())
        now = utc_now()
        with self._connect() as connection:
            connection.execute("""insert into content_items(id,title,content_type,business_objective,audience,primary_keyword,search_intent,related_products,source_evidence_json,body,status,owner,due_date,ai_draft,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (content_id, title, content_type, business_objective, audience, primary_keyword, search_intent, related_products, json.dumps(redact_mapping(source_evidence or []), default=str), body, status, owner, due_date, int(ai_draft), actor.user_id, now, now))
            self._audit(connection, actor, "content.created", "content", content_id, {"title": title, "status": status, "ai_draft": ai_draft})
        return content_id

    def list_content_items(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute("select * from content_items order by due_date is null,due_date,created_at desc limit ?", (limit,)).fetchall()]

    def update_content(self, actor: UserIdentity, content_id: str, *, body: str, status: str) -> None:
        require_permission(actor.role, Permission.MANAGE_CONTENT)
        with self._connect() as connection:
            row = connection.execute("select status from content_items where id=?", (content_id,)).fetchone()
            if not row:
                raise KeyError("Content item not found.")
            connection.execute("update content_items set body=?,status=?,updated_at=? where id=?", (body, status, utc_now(), content_id))
            self._audit(connection, actor, "content.updated", "content", content_id, {"from": row["status"], "to": status})

    def create_experiment(self, actor: UserIdentity, **fields: Any) -> str:
        require_permission(actor.role, Permission.MANAGE_TASKS)
        experiment_id = str(uuid.uuid4())
        now = utc_now()
        values = (
            experiment_id,
            fields["name"],
            fields["hypothesis"],
            fields.get("affected_entity", ""),
            fields.get("baseline_metric", ""),
            fields.get("target_metric", ""),
            fields.get("start_date"),
            fields.get("end_date"),
            fields.get("audience", ""),
            fields.get("control_description", ""),
            fields.get("variant_description", ""),
            fields.get("confidence_limitation", ""),
            fields.get("status", "Proposed"),
            fields.get("result", ""),
            fields.get("decision", ""),
            fields.get("owner", actor.display_name),
            actor.user_id,
            now,
            now,
        )
        with self._connect() as connection:
            connection.execute("""insert into experiments(id,name,hypothesis,affected_entity,baseline_metric,target_metric,start_date,end_date,audience,control_description,variant_description,confidence_limitation,status,result,decision,owner,created_by,created_at,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
            self._audit(connection, actor, "experiment.created", "experiment", experiment_id, {"name": fields["name"]})
        return experiment_id

    def list_experiments(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute("select * from experiments order by created_at desc limit ?", (limit,)).fetchall()]

    def enqueue_job(self, actor: UserIdentity, job_type: str, payload: dict[str, Any], *, idempotency_key: str, max_retries: int = 5) -> str:
        require_permission(actor.role, Permission.MANAGE_TASKS)
        job_id = str(uuid.uuid4())
        with self._connect() as connection:
            try:
                connection.execute("insert into job_queue(id,job_type,payload_json,status,requested_by,requested_at,max_retries,idempotency_key) values(?,?,?,?,?,?,?,?)", (job_id, job_type, json.dumps(redact_mapping(payload), default=str), "Queued", actor.user_id, utc_now(), max_retries, idempotency_key))
            except sqlite3.IntegrityError:
                existing = connection.execute("select id from job_queue where idempotency_key=?", (idempotency_key,)).fetchone()
                if existing:
                    return str(existing["id"])
                raise
            self._audit(connection, actor, "job.enqueued", "job", job_id, {"job_type": job_type, "idempotency_key": idempotency_key})
        return job_id

    def list_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute("select * from job_queue order by requested_at desc limit ?", (limit,)).fetchall()]

    def list_audit_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [_decode_row(row) for row in connection.execute("select * from audit_log order by created_at desc limit ?", (limit,)).fetchall()]
