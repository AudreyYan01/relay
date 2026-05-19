from __future__ import annotations
from datetime import datetime
from typing import Any


def _days_since(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        return (datetime.now() - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).days
    except ValueError:
        return None


def generate_brief(donor: dict, transactions: list[dict], engagements: list[dict]) -> dict:
    name = donor.get("FullName") or "This supporter"
    first = name.split()[0] if name else "They"
    rel_type = donor.get("RelationshipType") or "PROSPECT"
    tier = donor.get("Tier") or "BRONZE"
    status = donor.get("Status") or "NEW"
    total_donated = float(donor.get("TotalDonated") or 0)
    interests = donor.get("Interests") or ""
    org = donor.get("Organization") or ""
    last_donation_at = donor.get("LastDonationAt")
    last_activity_at = donor.get("LastActivityAt")
    eng_count = int(donor.get("EngagementCount") or 0)

    days_since_donation = _days_since(last_donation_at)
    days_since_activity = _days_since(last_activity_at)

    # Most recent engagement name
    recent_event = None
    for e in engagements:
        if e.get("EngagementStatus") == "COMPLETED":
            recent_event = e.get("ActivityID")
            break

    recent_tx_type = transactions[0].get("TransactionType") if transactions else None
    donation_count = sum(1 for t in transactions if t.get("TransactionType") == "DONATION" and t.get("PaymentStatus") == "SUCCESS")

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
        summary = f"{name} is a newer contact with {eng_count} recorded engagements and ${total_donated:,.0f} in contributions."

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

    # --- Suggested next action ---
    if status == "LAPSED":
        next_action = f"Send a personalized check-in note to {first} referencing their past involvement. Invite them to an upcoming event."
    elif status == "ACTIVE" and tier in ("GOLD", "PLATINUM"):
        next_action = f"Schedule a one-on-one call or invite {first} to the next supporter gathering. Acknowledge their sustained commitment."
    elif status == "ACTIVE" and donation_count == 1:
        next_action = f"Send a thank-you message to {first} and share an impact story aligned with their interests ({interests or 'the mission'})."
    elif status == "WARM":
        next_action = f"Reach out to {first} with a relevant program update or event invitation to re-warm the relationship."
    elif rel_type == "VOLUNTEER":
        next_action = f"Follow up with {first} on their volunteer experience and explore deeper program involvement."
    elif rel_type == "PROSPECT" and eng_count >= 1:
        next_action = f"Invite {first} to make their first contribution — send a targeted giving ask tied to a program they've attended."
    else:
        next_action = f"Add {first} to the next event invite list and send a brief introductory message about current programs."

    return {
        "summary": summary,
        "why_matters": why_matters,
        "recent_signal": recent_signal,
        "risk_flag": risk_flag,
        "next_action": next_action,
    }
