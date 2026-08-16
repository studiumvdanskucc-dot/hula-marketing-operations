from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .models import UserIdentity
from .store import OperationalStore


CORE_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "stage": "Brief",
        "channel": "Campaign core",
        "task": "Confirm objective, primary KPI and baseline",
        "owner": "Marketing",
        "lead_days": 24,
        "gate": True,
        "action": "Write one measurable objective and document the metric source, formula and starting value.",
    },
    {
        "stage": "Brief",
        "channel": "Campaign core",
        "task": "Verify audience, consent and suppressions",
        "owner": "Marketing",
        "lead_days": 22,
        "gate": True,
        "action": "Name the audience, lawful basis/consent treatment and required suppression groups.",
    },
    {
        "stage": "Create",
        "channel": "Merchandising",
        "task": "Lock available products and fallback collection",
        "owner": "Merchandising",
        "lead_days": 18,
        "gate": True,
        "action": "Verify live inventory and provide a collection fallback for one-off items that sell before launch.",
    },
    {
        "stage": "Measure",
        "channel": "Measurement",
        "task": "Prepare UTMs, conversion checks and reporting view",
        "owner": "Marketing",
        "lead_days": 12,
        "gate": True,
        "action": "Create the UTM plan, test conversion events and state the attribution window for every channel.",
    },
    {
        "stage": "Approve",
        "channel": "Governance",
        "task": "Complete launch review and manager approval",
        "owner": "Administrator",
        "lead_days": 3,
        "gate": True,
        "action": "Review final assets, audience, destinations, budget, measurement and rollback plan.",
    },
    {
        "stage": "Learn",
        "channel": "Measurement",
        "task": "Review results against the agreed baseline",
        "owner": "Marketing",
        "after_days": 14,
        "gate": False,
        "action": "Compare source metrics to baseline, document limitations and decide whether to scale, change or stop.",
    },
)


CHANNEL_CHECKLIST: dict[str, tuple[dict[str, Any], ...]] = {
    "Google Ads": (
        {
            "stage": "Create",
            "task": "Review search intent, structure, negatives and landing-page fit",
            "owner": "Paid media",
            "lead_days": 14,
            "gate": True,
            "action": "Prepare a read-only recommendation covering brand/non-brand separation, search terms, negatives and landing-page relevance.",
        },
    ),
    "Meta Ads": (
        {
            "stage": "Create",
            "task": "Prepare creative rotation and verify catalogue availability",
            "owner": "Paid media",
            "lead_days": 14,
            "gate": True,
            "action": "Provide at least two creative angles, confirm live destinations and define the fatigue threshold.",
        },
    ),
    "Klaviyo": (
        {
            "stage": "Create",
            "task": "Build email brief, segment logic and suppression checklist",
            "owner": "Marketing",
            "lead_days": 12,
            "gate": True,
            "action": "Draft the message, audience rules, exclusions, links and test plan; keep sending disabled until approved.",
        },
    ),
    "Blog / SEO": (
        {
            "stage": "Create",
            "task": "Prepare evidence-backed content and internal links",
            "owner": "Marketing",
            "lead_days": 16,
            "gate": True,
            "action": "Create the brief and draft, attach evidence, verify product/authentication claims and plan measurement.",
        },
    ),
    "Landing page": (
        {
            "stage": "Create",
            "task": "Review landing-page message, mobile speed and product availability",
            "owner": "Marketing",
            "lead_days": 12,
            "gate": True,
            "action": "Verify the page promise, CTA, mobile experience, links and available inventory before approval.",
        },
    ),
    "Stores / GBP": (
        {
            "stage": "Create",
            "task": "Prepare store listing, staff brief and offline measurement",
            "owner": "Marketing",
            "lead_days": 10,
            "gate": True,
            "action": "Confirm opening/location details, store team instructions and a QR/code or survey for offline measurement.",
        },
    ),
    "Organic social": (
        {
            "stage": "Create",
            "task": "Prepare organic social assets and response plan",
            "owner": "Marketing",
            "lead_days": 9,
            "gate": False,
            "action": "Draft the channel-native assets, accessibility text, links and moderation/escalation notes.",
        },
    ),
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:64]


def campaign_checklist(campaign: dict[str, Any]) -> list[dict[str, Any]]:
    start_raw = campaign.get("start_date")
    try:
        start = date.fromisoformat(str(start_raw)) if start_raw else date.today() + timedelta(days=21)
    except ValueError:
        start = date.today() + timedelta(days=21)

    rows: list[dict[str, Any]] = []
    for item in CORE_CHECKLIST:
        rows.append(dict(item))
    for channel in campaign.get("channels") or []:
        for item in CHANNEL_CHECKLIST.get(str(channel), ()):  # unknown channels remain visible on the campaign record
            rows.append({"channel": str(channel), "gate": True, **item})

    for item in rows:
        if "after_days" in item:
            due = start + timedelta(days=int(item["after_days"]))
        else:
            due = start - timedelta(days=int(item.get("lead_days", 7)))
        item["due_date"] = due.isoformat()
        item["deduplication_key"] = f"campaign:{campaign['id']}:{_slug(item['channel'])}:{_slug(item['task'])}"
    return rows


def create_campaign_tasks(
    store: OperationalStore,
    actor: UserIdentity,
    campaign: dict[str, Any],
) -> list[str]:
    created: list[str] = []
    for item in campaign_checklist(campaign):
        task_id = store.create_task(
            actor,
            title=f"{campaign['name']} — {item['task']}",
            description=item["action"],
            problem_type=f"Campaign / {item['stage']}",
            source_system="Campaign workspace",
            source_entity=campaign["name"],
            evidence={
                "campaign_id": campaign["id"],
                "campaign": campaign["name"],
                "channel": item["channel"],
                "stage": item["stage"],
                "gate": item["gate"],
            },
            severity="High" if item["gate"] else "Medium",
            recommended_action=item["action"],
            owner=item["owner"],
            due_date=item["due_date"],
            success_measure="The checklist item is evidenced, reviewed and attached to the campaign decision record.",
            deduplication_key=item["deduplication_key"],
            data_mode="demo" if actor.demo else "live",
            related_entity_type="campaign",
            related_entity_id=campaign["id"],
            status="Planned",
        )
        created.append(task_id)
    return created


def campaign_tasks(store: OperationalStore, campaign_id: str) -> list[dict[str, Any]]:
    return [
        task
        for task in store.list_tasks()
        if task.get("related_entity_type") == "campaign" and task.get("related_entity_id") == campaign_id
    ]


def readiness_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    completed_states = {"Completed", "Implemented", "Approved"}
    total = len(tasks)
    completed = sum(task.get("status") in completed_states for task in tasks)
    blocked = sum(task.get("status") in {"Rejected", "Verification Failed"} for task in tasks)
    return {
        "total": total,
        "completed": completed,
        "blocked": blocked,
        "pct": round(100 * completed / total) if total else 0,
        "label": "Ready" if total and completed == total and blocked == 0 else "Work in progress" if total else "Checklist not created",
    }
