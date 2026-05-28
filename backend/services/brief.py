from __future__ import annotations
from datetime import datetime
import json

RULE_VERSION = "v1"


def _days_since(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        return (datetime.now() - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).days
    except ValueError:
        return None


def _pick_action(
    status: str,
    tier: str,
    donation_count: int,
    rel_type: str,
    eng_count: int,
    interests: str,
    first: str,
    dismissed: set,
) -> tuple[str, str]:
    """Return (action_type, action_text), skipping recently-dismissed action types."""
    candidates: list[tuple[str, str]] = []

    if status == "LAPSED":
        candidates.append((
            "reactivate_lapsed",
            f"Send a personalized check-in note to {first} referencing their past involvement. Invite them to an upcoming event.",
        ))
    if status == "ACTIVE" and tier in ("GOLD", "PLATINUM"):
        candidates.append((
            "steward_vip",
            f"Schedule a one-on-one call or invite {first} to the next supporter gathering. Acknowledge their sustained commitment.",
        ))
    if status == "ACTIVE" and donation_count == 1:
        candidates.append((
            "thankyou_first",
            f"Send a thank-you message to {first} and share an impact story aligned with their interests ({interests or 'the mission'}).",
        ))
    if status == "WARM":
        candidates.append((
            "rewarm_warm",
            f"Reach out to {first} with a relevant program update or event invitation to re-warm the relationship.",
        ))
    if rel_type == "VOLUNTEER":
        candidates.append((
            "volunteer_followup",
            f"Follow up with {first} on their volunteer experience and explore deeper program involvement.",
        ))
    if rel_type == "PROSPECT" and eng_count >= 1:
        candidates.append((
            "prospect_firstask",
            f"Invite {first} to make their first contribution — send a targeted giving ask tied to a program they've attended.",
        ))
    candidates.append((
        "default_invite",
        f"Add {first} to the next event invite list and send a brief introductory message about current programs.",
    ))

    for action_type, action_text in candidates:
        if action_type not in dismissed:
            return action_type, action_text
    return candidates[-1]


def generate_brief(
    donor: dict,
    transactions: list[dict],
    engagements: list[dict],
    dismissed_action_types: set | None = None,
) -> dict:
    name = donor.get("FullName") or "This supporter"
    first = name.split()[0] if name else "They"
    rel_type = donor.get("RelationshipType") or "PROSPECT"
    tier = donor.get("Tier") or "BRONZE"
    # StatusOverride takes precedence; Status is always kept in sync by the API
    status = donor.get("StatusOverride") or donor.get("Status") or "NEW"
    total_donated = float(donor.get("TotalDonated") or 0)
    interests = donor.get("Interests") or ""
    last_donation_at = donor.get("LastDonationAt")
    last_activity_at = donor.get("LastActivityAt")
    eng_count = int(donor.get("EngagementCount") or 0)

    days_since_donation = _days_since(last_donation_at)
    days_since_activity = _days_since(last_activity_at)

    donation_count = sum(
        1 for t in transactions
        if t.get("TransactionType") == "DONATION" and t.get("PaymentStatus") == "SUCCESS"
    )

    # --- Summary ---
    if status == "ACTIVE" and donation_count >= 2:
        role_label = "supporter" if rel_type == "DONOR" else rel_type.lower()
        summary = (
            f"{name} is a loyal {role_label} who has donated {donation_count} times"
            f" (${total_donated:,.0f} total)."
        )
    elif status == "ACTIVE" and eng_count >= 2:
        summary = (
            f"{name} is an active community member with {eng_count} completed engagements"
            f" and ${total_donated:,.0f} in contributions."
        )
    elif status == "WARM":
        summary = (
            f"{name} has been engaged in the past but activity has slowed."
            f" Last interaction was {days_since_activity or '—'} days ago."
        )
    elif status == "LAPSED":
        summary = (
            f"{name} was previously active but has not engaged in over 4 months."
            f" Total contributions: ${total_donated:,.0f}."
        )
    else:
        summary = (
            f"{name} is a newer contact with {eng_count} recorded engagements"
            f" and ${total_donated:,.0f} in contributions."
        )

    # --- Why this supporter matters ---
    if tier in ("GOLD", "PLATINUM"):
        why_matters = f"{first} is a {tier.lower()}-tier supporter — among the organization's highest contributors."
    elif rel_type == "VOLUNTEER":
        why_matters = f"{first} contributes time and skills as a volunteer, which amplifies program capacity."
    elif rel_type == "SPONSOR":
        why_matters = f"{first} represents a sponsorship relationship with institutional giving potential."
    elif donation_count >= 1 and status in ("ACTIVE", "WARM"):
        why_matters = f"{first} has demonstrated financial commitment and continued interest in the mission."
    else:
        why_matters = f"{first} is a prospective relationship worth nurturing — early cultivation can yield long-term value."

    # --- Recent signal ---
    if days_since_activity is not None and days_since_activity <= 14:
        recent_signal = f"Engaged within the last {days_since_activity} day(s)."
    elif days_since_donation is not None and days_since_donation <= 30:
        recent_signal = f"Donated ${transactions[0].get('TransactionAmount', 0):,.0f} {days_since_donation} day(s) ago."
    elif days_since_activity is not None:
        recent_signal = f"Last activity was {days_since_activity} days ago."
    else:
        recent_signal = "No recent engagement signals recorded."

    # --- Risk / opportunity flag ---
    if status == "LAPSED" and total_donated >= 100:
        risk_flag = "RE-ENGAGEMENT OPPORTUNITY: High-value lapsed supporter. Timely outreach could recapture relationship."
    elif status == "WARM" and days_since_activity and days_since_activity > 60:
        risk_flag = "AT RISK: Engagement declining. Consider proactive outreach before lapse."
    elif status == "ACTIVE" and tier in ("GOLD", "PLATINUM"):
        risk_flag = "RETENTION PRIORITY: Top-tier active supporter. High touch engagement is warranted."
    elif status == "NEW" and eng_count == 0:
        risk_flag = "NEW CONTACT: No engagement recorded yet. First touch is critical."
    else:
        risk_flag = None

    # --- Suggested next action (disposition-aware) ---
    dismissed = dismissed_action_types or set()
    action_type, next_action = _pick_action(
        status, tier, donation_count, rel_type, eng_count, interests, first, dismissed
    )

    input_snapshot = json.dumps({
        "status": status,
        "tier": tier,
        "donation_count": donation_count,
        "days_since_activity": days_since_activity,
        "days_since_donation": days_since_donation,
        "eng_count": eng_count,
        "rel_type": rel_type,
        "rule_version": RULE_VERSION,
        "dismissed_action_types": list(dismissed),
    })

    return {
        "summary": summary,
        "why_matters": why_matters,
        "recent_signal": recent_signal,
        "risk_flag": risk_flag,
        "next_action": next_action,
        # internal fields used by main.py for logging — not forwarded to client
        "action_type": action_type,
        "rule_version": RULE_VERSION,
        "input_snapshot": input_snapshot,
    }
