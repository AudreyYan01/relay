import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid

from fastapi.middleware.cors import CORSMiddleware
from services.rollups import recompute_donor_rollups
from services.brief import generate_brief


app = FastAPI()


@app.on_event("startup")
def _ensure_schema():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS RecommendationLog (
            LogID        TEXT PRIMARY KEY,
            DonorID      TEXT NOT NULL,
            SuggestedAction TEXT NOT NULL,
            ActionType   TEXT NOT NULL,
            RuleVersion  TEXT NOT NULL DEFAULT 'v1',
            InputSnapshot TEXT,
            Disposition  TEXT CHECK (
                Disposition IN ('accepted','edited','dismissed','deferred')
                OR Disposition IS NULL
            ),
            Rationale    TEXT,
            EditedAction TEXT,
            CreatedAt    TEXT NOT NULL DEFAULT (datetime('now')),
            DisposedAt   TEXT,
            FOREIGN KEY (DonorID) REFERENCES Donor(DonorID) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reclog_donor ON RecommendationLog(DonorID, CreatedAt)"
    )
    conn.commit()
    conn.close()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "app.db"


def get_conn():
    """
    Create and return a SQLite connection to the app database.

    What it does:
    - Opens a connection to the SQLite DB file at DB_PATH.
    - Sets `row_factory` so query results behave like dict-like rows
      (so we can convert rows into JSON easily).
    - Enables foreign key enforcement for SQLite (off by default).

    Why we do this:
    - We want every endpoint to talk to the same DB consistently.
    - We want FK constraints to actually work (data integrity).
    - We want API responses to be easy to serialize to JSON.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@app.get("/health")
def health():
    """
    Health check endpoint.

    What it does:
    - Returns a simple JSON payload indicating the server is running.

    Why we do this:
    - Useful for quick sanity checks (browser, curl, monitoring).
    - Confirms FastAPI app is alive without touching the DB.
    """
    return {"status": "ok"}


@app.get("/donors")
def get_donors(
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    relationship_type: Optional[str] = None,
):
    conn = get_conn()

    query = """
        SELECT
            DonorID, FullName, Email, City, State,
            RelationshipType, Organization, Interests,
            Status, Tier, TotalDonated, LastDonationAt, LastActivityAt,
            EngagementCount, FollowUpStatus, PriorityScore
        FROM Donor
        WHERE 1=1
    """
    params: list = []

    if search:
        query += " AND FullName LIKE ?"
        params.append(f"%{search}%")

    if status:
        query += " AND Status = ?"
        params.append(status.upper())

    if relationship_type:
        query += " AND RelationshipType = ?"
        params.append(relationship_type.upper())

    query += " ORDER BY PriorityScore DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/dashboard")
def get_dashboard():
    conn = get_conn()

    total_supporters = conn.execute("SELECT COUNT(*) FROM Donor").fetchone()[0]
    total_donated = conn.execute(
        "SELECT COALESCE(SUM(TotalDonated), 0) FROM Donor"
    ).fetchone()[0]
    followup_needed = conn.execute(
        "SELECT COUNT(*) FROM Donor WHERE FollowUpStatus = 'NOT_STARTED' AND Status != 'NEW'"
    ).fetchone()[0]
    high_priority = conn.execute(
        "SELECT COUNT(*) FROM Donor WHERE PriorityScore >= 50"
    ).fetchone()[0]

    top_donors = conn.execute(
        """
        SELECT DonorID, FullName, Tier, Status, PriorityScore,
               FollowUpStatus, TotalDonated, LastActivityAt
        FROM Donor
        ORDER BY TotalDonated DESC
        LIMIT 10
        """
    ).fetchall()

    recent_donations = conn.execute(
        """
        SELECT
            t.TransactionID, t.DonorID, d.FullName,
            t.TransactionAmount, t.TransactionDateTime
        FROM "Transaction" t
        JOIN Donor d ON d.DonorID = t.DonorID
        WHERE t.PaymentStatus = 'SUCCESS' AND t.TransactionType = 'DONATION'
        ORDER BY t.TransactionDateTime DESC
        LIMIT 8
        """
    ).fetchall()

    recent_event = conn.execute(
        """
        SELECT ActivityName, ActivityStartTime
        FROM Activity
        WHERE ActivityStartTime IS NOT NULL
        ORDER BY ActivityStartTime DESC
        LIMIT 1
        """
    ).fetchone()

    conn.close()
    return {
        "total_supporters": total_supporters,
        "total_donated": round(float(total_donated), 2),
        "followup_needed": followup_needed,
        "high_priority": high_priority,
        "top_donors": [dict(r) for r in top_donors],
        "recent_donations": [dict(r) for r in recent_donations],
        "recent_event": dict(recent_event) if recent_event else None,
    }

@app.get("/donors/{donor_id}")
def donor_detail(donor_id: str, tx_limit: int = 20, activity_limit: int = 20):
    """
    Donor profile endpoint: fetch donor + recent transactions + recent engagements.

    Path inputs:
    - donor_id: DonorID (UUID string)

    Query inputs:
    - tx_limit: number of recent transactions to return
    - activity_limit: number of recent engagements (DonorActivity) to return

    What it does:
    1) Fetches the Donor row (the donor "profile" / master record).
    2) Fetches recent Transaction rows for that donor.
    3) Fetches recent DonorActivity rows for that donor.
    4) Returns a single JSON object containing:
       - donor
       - transactions[]
       - engagements[]

    Why we do this:
    - This powers the MVP "donor profile" view.
    - It gives operators a single place to see donor history.
    - It becomes the canonical structured input for later AI summaries.
    """
    conn = get_conn()

    donor = conn.execute(
        """
        SELECT *
        FROM Donor
        WHERE DonorID = ?
        """,
        (donor_id,),
    ).fetchone()

    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    transactions = conn.execute(
        """
        SELECT
            TransactionID, TransactionDateTime, TransactionType, TransactionItem,
            Quantity, TransactionPrice, TransactionAmount,
            PaymentMethod, PaymentStatus, ReceiptSent, IsTaxDeductible,
            ActivityID
        FROM "Transaction"
        WHERE DonorID = ?
        ORDER BY TransactionDateTime DESC
        LIMIT ?
        """,
        (donor_id, tx_limit),
    ).fetchall()

    engagements = conn.execute(
        """
        SELECT
            da.DonorActivityID, da.ActivityID,
            a.ActivityName,
            da.EngagementRole, da.EngagementType, da.EngagementStatus,
            da.EngagedAt, da.ParticipateStartAt, da.Notes
        FROM DonorActivity da
        LEFT JOIN Activity a ON a.ActivityID = da.ActivityID
        WHERE da.DonorID = ?
        ORDER BY COALESCE(da.ParticipateStartAt, da.EngagedAt) DESC
        LIMIT ?
        """,
        (donor_id, activity_limit),
    ).fetchall()

    try:
        touchpoints = conn.execute(
            """
            SELECT TouchpointID, Note, CreatedAt
            FROM Touchpoint
            WHERE DonorID = ?
            ORDER BY CreatedAt DESC
            LIMIT 50
            """,
            (donor_id,),
        ).fetchall()
    except Exception:
        touchpoints = []

    conn.close()

    return {
        "donor": dict(donor),
        "transactions": [dict(r) for r in transactions],
        "engagements": [dict(r) for r in engagements],
        "touchpoints": [dict(r) for r in touchpoints],
    }


@app.get("/donors/{donor_id}/brief")
def get_donor_brief(donor_id: str):
    conn = get_conn()

    donor = conn.execute("SELECT * FROM Donor WHERE DonorID = ?", (donor_id,)).fetchone()
    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    transactions = conn.execute(
        """
        SELECT TransactionID, TransactionType, TransactionAmount, PaymentStatus, TransactionDateTime
        FROM "Transaction" WHERE DonorID = ? ORDER BY TransactionDateTime DESC LIMIT 20
        """,
        (donor_id,),
    ).fetchall()

    engagements = conn.execute(
        """
        SELECT DonorActivityID, ActivityID, EngagementType, EngagementStatus,
               EngagedAt, ParticipateStartAt
        FROM DonorActivity WHERE DonorID = ?
        ORDER BY COALESCE(ParticipateStartAt, EngagedAt) DESC LIMIT 20
        """,
        (donor_id,),
    ).fetchall()

    # Action types the user dismissed in the last 60 days → skip in this recommendation.
    dismissed_rows = conn.execute(
        """
        SELECT DISTINCT ActionType FROM RecommendationLog
        WHERE DonorID = ?
          AND Disposition = 'dismissed'
          AND DisposedAt >= datetime('now', '-60 days')
        """,
        (donor_id,),
    ).fetchall()
    dismissed_action_types = {row[0] for row in dismissed_rows}

    brief = generate_brief(
        dict(donor),
        [dict(r) for r in transactions],
        [dict(r) for r in engagements],
        dismissed_action_types,
    )

    log_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO RecommendationLog (LogID, DonorID, SuggestedAction, ActionType, RuleVersion, InputSnapshot)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (log_id, donor_id, brief["next_action"], brief["action_type"], brief["rule_version"], brief["input_snapshot"]),
    )
    conn.commit()
    conn.close()

    return {
        "summary": brief["summary"],
        "why_matters": brief["why_matters"],
        "recent_signal": brief["recent_signal"],
        "risk_flag": brief["risk_flag"],
        "next_action": brief["next_action"],
        "log_id": log_id,
    }


class FollowUpUpdate(BaseModel):
    status: Literal["NOT_STARTED", "PLANNED", "COMPLETED"]


@app.patch("/donors/{donor_id}/followup")
def update_followup(donor_id: str, payload: FollowUpUpdate):
    conn = get_conn()
    donor = conn.execute("SELECT DonorID FROM Donor WHERE DonorID = ?", (donor_id,)).fetchone()
    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    conn.execute(
        "UPDATE Donor SET FollowUpStatus = ?, UpdatedAt = datetime('now') WHERE DonorID = ?",
        (payload.status, donor_id),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT DonorID, FullName, FollowUpStatus FROM Donor WHERE DonorID = ?", (donor_id,)
    ).fetchone()
    conn.close()
    return dict(updated)


class DispositionCreate(BaseModel):
    disposition: Literal["accepted", "edited", "dismissed", "deferred"]
    rationale: Optional[str] = None
    edited_action: Optional[str] = None


@app.post("/donors/{donor_id}/recommendation/{log_id}/disposition")
def record_disposition(donor_id: str, log_id: str, payload: DispositionCreate):
    conn = get_conn()

    log = conn.execute(
        "SELECT LogID FROM RecommendationLog WHERE LogID = ? AND DonorID = ?",
        (log_id, donor_id),
    ).fetchone()
    if log is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Recommendation log not found")

    conn.execute(
        """
        UPDATE RecommendationLog
        SET Disposition = ?, Rationale = ?, EditedAction = ?, DisposedAt = datetime('now')
        WHERE LogID = ?
        """,
        (payload.disposition, payload.rationale, payload.edited_action, log_id),
    )

    # Accepting a suggestion signals intent to act → move follow-up to PLANNED.
    if payload.disposition in ("accepted", "edited"):
        conn.execute(
            """UPDATE Donor
               SET FollowUpStatus = 'PLANNED', UpdatedAt = datetime('now')
               WHERE DonorID = ? AND FollowUpStatus = 'NOT_STARTED'""",
            (donor_id,),
        )

    conn.commit()
    result = conn.execute(
        "SELECT LogID, Disposition, Rationale, EditedAction, DisposedAt FROM RecommendationLog WHERE LogID = ?",
        (log_id,),
    ).fetchone()
    conn.close()
    return dict(result)


class TouchpointCreate(BaseModel):
    note: str


@app.post("/donors/{donor_id}/touchpoints")
def add_touchpoint(donor_id: str, payload: TouchpointCreate):
    conn = get_conn()
    donor = conn.execute("SELECT DonorID FROM Donor WHERE DonorID = ?", (donor_id,)).fetchone()
    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    tp_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO Touchpoint (TouchpointID, DonorID, Note) VALUES (?, ?, ?)",
        (tp_id, donor_id, payload.note.strip()),
    )
    conn.commit()
    tp = conn.execute(
        "SELECT TouchpointID, Note, CreatedAt FROM Touchpoint WHERE TouchpointID = ?", (tp_id,)
    ).fetchone()
    conn.close()
    return dict(tp)


class StatusOverrideUpdate(BaseModel):
    status: Optional[Literal["NEW", "ACTIVE", "WARM", "LAPSED"]] = None


@app.patch("/donors/{donor_id}/status")
def override_status(donor_id: str, payload: StatusOverrideUpdate):
    conn = get_conn()
    donor = conn.execute("SELECT DonorID FROM Donor WHERE DonorID = ?", (donor_id,)).fetchone()
    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    if payload.status is not None:
        # Apply override immediately to both columns so Status is always the effective status.
        conn.execute(
            "UPDATE Donor SET StatusOverride = ?, Status = ?, UpdatedAt = datetime('now') WHERE DonorID = ?",
            (payload.status, payload.status, donor_id),
        )
        conn.commit()
    else:
        # Clear override and recompute Status from donation/activity recency.
        conn.execute(
            "UPDATE Donor SET StatusOverride = NULL, UpdatedAt = datetime('now') WHERE DonorID = ?",
            (donor_id,),
        )
        recompute_donor_rollups(conn, donor_id)
        conn.commit()

    updated = conn.execute(
        "SELECT DonorID, FullName, Status, StatusOverride FROM Donor WHERE DonorID = ?", (donor_id,)
    ).fetchone()
    conn.close()
    return dict(updated)


@app.get("/events")
def get_events():
    conn = get_conn()
    # Correlated subqueries avoid the Cartesian product that inflated revenue
    # when an activity has both multiple DonorActivity rows and multiple Transactions.
    rows = conn.execute(
        """
        SELECT
            a.ActivityID,
            a.ActivityName,
            a.ActivityStartTime,
            a.ActivityEndTime,
            a.ListPrice,
            (
                SELECT COUNT(DISTINCT da.DonorID)
                FROM DonorActivity da
                WHERE da.ActivityID = a.ActivityID
                  AND da.EngagementStatus = 'COMPLETED'
            ) AS attendee_count,
            (
                SELECT COALESCE(SUM(t.TransactionAmount), 0)
                FROM "Transaction" t
                WHERE t.ActivityID = a.ActivityID
                  AND t.PaymentStatus = 'SUCCESS'
            ) AS total_revenue
        FROM Activity a
        ORDER BY a.ActivityStartTime DESC NULLS LAST
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


#######################################################################################
## POST endpoint to recompute donor rollups
class TransactionCreate(BaseModel):
    """
    Request schema (input contract) for POST /transactions.

    What it represents:
    - A single transaction event tied to a donor (and optionally an activity).

    Why we do this:
    - FastAPI + Pydantic validates the payload automatically.
    - This becomes your stable API contract for UI / clients.
    - We enforce types + constraints (e.g., quantity >= 1).
    """
    donor_id: str = Field(..., description="DonorID (UUID string)")
    activity_id: Optional[str] = Field(None, description="ActivityID (optional)")

    transaction_datetime: Optional[str] = Field(
        None,
        description="Timestamp 'YYYY-MM-DD HH:MM:SS'. Defaults to now() if omitted.",
    )

    quantity: int = Field(1, ge=1)
    transaction_price: float = Field(..., ge=0)
    transaction_amount: Optional[float] = Field(
        None,
        ge=0,
        description="If omitted, computed as transaction_price * quantity",
    )

    currency: str = Field("USD", min_length=3, max_length=3)

    transaction_type: Literal["DONATION", "TICKET", "MERCH", "FEE", "OTHER"]
    transaction_item: Optional[str] = None

    payment_method: str
    payment_status: Literal["SUCCESS", "FAIL", "REFUNDED"] = "SUCCESS"

    receipt_sent: bool = False
    is_tax_deductible: bool = False


def _now_str() -> str:
    """
    Return current time formatted as 'YYYY-MM-DD HH:MM:SS'.

    Why we do this:
    - SQLite timestamps are stored as TEXT in this MVP.
    - Using a consistent string format makes sorting and parsing reliable.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DonorCreate(BaseModel):
    """
    Request schema for creating a donor.

    MVP rule:
    - If Email is provided, we treat it as the primary lookup key (case-insensitive).
    - Else if PhoneNumber is provided, we use it as a secondary lookup key.
    - If a match exists, return the existing donor instead of creating a new one.
    """

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None

    preferred_contact_method: Literal["EMAIL", "PHONE", "SMS", "NONE"] = "EMAIL"

    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"


@app.post("/donors")
def create_donor(payload: DonorCreate):
    """
    Create a donor (or return an existing donor) using deterministic matching.

    Matching logic:
    1) If email provided -> match by lower(email)
    2) Else if phone provided -> match by exact phone
    3) Else -> always create a new donor (no reliable identifier)

    Returns:
    - { "created": bool, "donor": {...} }
    """
    conn = get_conn()

    # --- 1) Lookup existing donor ---
    existing = None

    if payload.email:
        existing = conn.execute(
            """
            SELECT *
            FROM Donor
            WHERE lower(Email) = lower(?)
            LIMIT 1
            """,
            (payload.email.strip(),),
        ).fetchone()

    if existing is None and payload.phone_number:
        existing = conn.execute(
            """
            SELECT *
            FROM Donor
            WHERE PhoneNumber = ?
            LIMIT 1
            """,
            (payload.phone_number.strip(),),
        ).fetchone()

    if existing is not None:
        conn.close()
        return {"created": False, "donor": dict(existing)}

    # --- 2) Create new donor ---
    donor_id = str(uuid.uuid4())

    # Normalize email to lower for storage consistency (optional but helpful)
    email_norm = payload.email.strip().lower() if payload.email else None
    phone_norm = payload.phone_number.strip() if payload.phone_number else None

    conn.execute(
        """
        INSERT INTO Donor (
            DonorID, FullName, Email, PhoneNumber,
            PreferredContactMethod, City, State, Country,
            CreatedAt, UpdatedAt
        ) VALUES (?,?,?,?,?,?,?,?, datetime('now'), datetime('now'))
        """,
        (
            donor_id,
            payload.full_name,
            email_norm,
            phone_norm,
            payload.preferred_contact_method,
            payload.city,
            payload.state,
            payload.country,
        ),
    )

    donor = conn.execute(
        "SELECT * FROM Donor WHERE DonorID = ?",
        (donor_id,),
    ).fetchone()

    conn.commit()
    conn.close()

    return {"created": True, "donor": dict(donor)}



@app.post("/transactions")
def create_transaction(payload: TransactionCreate):
    """
    Create a transaction record and recompute the donor's rollups.

    Input:
    - payload: TransactionCreate (validated by Pydantic)

    What it does (high-level):
    1) Validates Donor exists (so we don't create orphan transactions).
    2) Validates Activity exists if provided.
    3) Normalizes/validates timestamps and computes amount if missing.
    4) Inserts a row into Transaction.
    5) Calls the deterministic rollup function to update:
       - TotalTransactionAmount, TotalDonated
       - LastDonationAt, LastActivityAt
       - Status, Tier
    6) Returns:
       - the new transaction_id
       - updated donor summary fields (so the UI sees instant impact)

    Why we do this:
    - This is the MVP "Act → Observe impact" loop.
    - It keeps financial truth in Transaction.
    - It keeps Donor cached fields updated for fast reads and clear reporting.
    """
    conn = get_conn()

    # 1) Validate donor exists
    donor = conn.execute(
        "SELECT DonorID FROM Donor WHERE DonorID = ?",
        (payload.donor_id,),
    ).fetchone()
    if donor is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Donor not found")

    # 2) Validate activity exists if provided
    if payload.activity_id:
        act = conn.execute(
            "SELECT ActivityID FROM Activity WHERE ActivityID = ?",
            (payload.activity_id,),
        ).fetchone()
        if act is None:
            conn.close()
            raise HTTPException(status_code=400, detail="ActivityID not found")

    # 3) Normalize datetime and amount
    tx_dt = payload.transaction_datetime or _now_str()
    try:
        datetime.strptime(tx_dt, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="transaction_datetime must be 'YYYY-MM-DD HH:MM:SS'",
        )

    amount = payload.transaction_amount
    if amount is None:
        amount = round(payload.transaction_price * payload.quantity, 2)

    # 4) Insert transaction
    tx_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO "Transaction" (
            TransactionID, DonorID, ActivityID, TransactionDateTime,
            Quantity, TransactionPrice, TransactionAmount, Currency,
            TransactionType, TransactionItem, PaymentMethod, PaymentStatus,
            ReceiptSent, IsTaxDeductible
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            tx_id,
            payload.donor_id,
            payload.activity_id,
            tx_dt,
            payload.quantity,
            float(payload.transaction_price),
            float(amount),
            payload.currency.upper(),
            payload.transaction_type,
            payload.transaction_item,
            payload.payment_method,
            payload.payment_status,
            1 if payload.receipt_sent else 0,
            1 if payload.is_tax_deductible else 0,
        ),
    )

    # 5) Recompute donor rollups deterministically
    recompute_donor_rollups(conn, payload.donor_id)

    # 6) Return updated donor summary + created transaction id
    updated = conn.execute(
        """
        SELECT
            DonorID, FullName, Email, City, State,
            Status, Tier, TotalDonated, TotalTransactionAmount,
            LastDonationAt, LastActivityAt
        FROM Donor
        WHERE DonorID = ?
        """,
        (payload.donor_id,),
    ).fetchone()

    conn.commit()
    conn.close()

    return {
        "transaction_id": tx_id,
        "donor": dict(updated) if updated else None,
    }