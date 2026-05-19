from __future__ import annotations

from datetime import datetime
import sqlite3


def recompute_donor_rollups(conn: sqlite3.Connection, donor_id: str) -> None:
    """
    Recompute deterministic donor rollups for a single donor.

    Authoritative sources:
      - TransactionTable (financial truth)
      - DonorActivity (engagement truth)

    This function updates cached fields on Donor:
      - TotalTransactionAmount
      - TotalDonated
      - LastDonationAt
      - LastActivityAt
      - Status
      - Tier

    Notes:
      - Status is based on recency of (LastDonationAt, LastActivityAt).
      - Tier is based on TotalDonated thresholds.
    """

    # 1) TotalTransactionAmount (SUCCESS only)
    conn.execute(
        """
        UPDATE Donor
        SET TotalTransactionAmount = (
            SELECT COALESCE(SUM(t.TransactionAmount), 0)
            FROM "Transaction" t
            WHERE t.DonorID = Donor.DonorID
              AND t.PaymentStatus = 'SUCCESS'
        )
        WHERE DonorID = ?
        """,
        (donor_id,),
    )

    # 2) TotalDonated + LastDonationAt (SUCCESS + DONATION only)
    conn.execute(
        """
        UPDATE Donor
        SET
            TotalDonated = (
                SELECT COALESCE(SUM(t.TransactionAmount), 0)
                FROM "Transaction" t
                WHERE t.DonorID = Donor.DonorID
                  AND t.PaymentStatus = 'SUCCESS'
                  AND t.TransactionType = 'DONATION'
            ),
            LastDonationAt = (
                SELECT MAX(t.TransactionDateTime)
                FROM "Transaction" t
                WHERE t.DonorID = Donor.DonorID
                  AND t.PaymentStatus = 'SUCCESS'
                  AND t.TransactionType = 'DONATION'
            )
        WHERE DonorID = ?
        """,
        (donor_id,),
    )

    # 3) LastActivityAt (COMPLETED engagements only)
    conn.execute(
        """
        UPDATE Donor
        SET LastActivityAt = (
            SELECT MAX(COALESCE(da.ParticipateStartAt, da.EngagedAt))
            FROM DonorActivity da
            WHERE da.DonorID = Donor.DonorID
              AND da.EngagementStatus = 'COMPLETED'
        )
        WHERE DonorID = ?
        """,
        (donor_id,),
    )

    # 4) Compute Status based on recency of last donation/activity
    row = conn.execute(
        """
        SELECT LastDonationAt, LastActivityAt, TotalDonated
        FROM Donor
        WHERE DonorID = ?
        """,
        (donor_id,),
    ).fetchone()

    if row is None:
        return

    last_don, last_act, total_don = row
    candidates = []

    for ts in (last_don, last_act):
        if ts:
            # expected format: "YYYY-MM-DD HH:MM:SS"
            candidates.append(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))

    if not candidates:
        status = "NEW"
    else:
        last = max(candidates)
        days_since = (datetime.now() - last).days
        if days_since <= 30:
            status = "ACTIVE"
        elif days_since <= 120:
            status = "WARM"
        else:
            status = "LAPSED"

    # 5) Tier based on TotalDonated
    td = float(total_don or 0)
    if td >= 2000:
        tier = "PLATINUM"
    elif td >= 500:
        tier = "GOLD"
    elif td >= 100:
        tier = "SILVER"
    else:
        tier = "BRONZE"

    # 6) EngagementCount (COMPLETED only)
    conn.execute(
        """
        UPDATE Donor
        SET EngagementCount = (
            SELECT COUNT(*)
            FROM DonorActivity da
            WHERE da.DonorID = Donor.DonorID
              AND da.EngagementStatus = 'COMPLETED'
        )
        WHERE DonorID = ?
        """,
        (donor_id,),
    )

    eng_row = conn.execute(
        "SELECT EngagementCount FROM Donor WHERE DonorID = ?", (donor_id,)
    ).fetchone()
    eng_count = int(eng_row[0] or 0) if eng_row else 0

    # PriorityScore: weighted formula (0–100 scale)
    #   40 pts from donation tier, 30 pts from recency, 30 pts from engagement depth
    tier_pts = {"BRONZE": 5, "SILVER": 20, "GOLD": 35, "PLATINUM": 40}.get(tier, 0)

    if not candidates:
        recency_pts = 0
    else:
        days_since = (datetime.now() - max(candidates)).days
        recency_pts = max(0, 30 - int(days_since / 5))  # full 30 pts if <5 days, 0 at 150+

    eng_pts = min(30, eng_count * 6)  # 6 pts per completed engagement, cap at 30

    priority = round(tier_pts + recency_pts + eng_pts, 1)

    conn.execute(
        """
        UPDATE Donor
        SET Status = CASE WHEN StatusOverride IS NOT NULL THEN StatusOverride ELSE ? END,
            Tier = ?,
            PriorityScore = ?
        WHERE DonorID = ?
        """,
        (status, tier, priority, donor_id),
    )