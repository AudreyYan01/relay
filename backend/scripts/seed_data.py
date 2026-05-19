import os
import sqlite3
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

BASE_DIR = Path(__file__).resolve().parents[1]  # backend/
DB_PATH = BASE_DIR / "data" / "app.db"

# How much data to generate
N_DONORS = 50
N_ACTIVITIES = 18
MAX_ENGAGEMENTS_PER_DONOR = 6
AVG_TX_PER_DONOR = 2.4

FIRST = ["Alex","Sam","Taylor","Jordan","Casey","Riley","Morgan","Jamie","Avery","Cameron","Dana","Quinn","Kai","Zoey","Noah","Maria","David","Sarah","James","Emma"]
LAST = ["Lee","Patel","Kim","Chen","Garcia","Nguyen","Brown","Davis","Wilson","Martinez","Lopez","Singh","Wang","Johnson","Thompson","White","Harris","Clark","Lewis","Robinson"]
CITIES = [
    ("San Francisco","CA","94107"),
    ("San Jose","CA","95112"),
    ("Oakland","CA","94612"),
    ("Mountain View","CA","94040"),
    ("Palo Alto","CA","94301"),
    ("Berkeley","CA","94704"),
]
PREF = ["EMAIL","PHONE","SMS","NONE"]

REL_TYPES = ["DONOR","VOLUNTEER","SPONSOR","PROSPECT"]
REL_WEIGHTS = [50, 20, 10, 20]

ORGS = [
    "Bay Area Tech Collective", "UCSF Medical Center", "Google", "Salesforce",
    "Stanford University", "City of San Francisco", "Caltrain", "Kaiser Permanente",
    "Genentech", "Wells Fargo", "Gap Inc.", "Levi Strauss", None, None, None,
]

INTEREST_POOL = [
    "youth education", "arts programming", "community events", "music",
    "environmental advocacy", "social justice", "food security", "mentorship",
    "housing", "public health", "tech for good", "literacy",
]

ROLE = ["AUDIENCE","VOLUNTEER","CUSTOMER","STAFF"]
ENG_TYPE = ["REGISTER","ATTEND","VOLUNTEER"]
ENG_STATUS = ["PLANNED","COMPLETED","CANCELLED","NO_SHOW"]

TX_TYPE = ["DONATION","TICKET","MERCH","FEE","OTHER"]
PAY_STATUS = ["SUCCESS","FAIL","REFUNDED"]
PAY_METHOD = ["CREDIT_CARD","ACH","CASH","CHECK","PAYPAL","OTHER"]


def uid() -> str:
    return str(uuid.uuid4())


def fmt_dt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def rand_dt(within_days: int = 365) -> datetime:
    now = datetime.now()
    d = timedelta(
        days=random.randint(0, within_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return now - d


def rand_date(within_days: int = 365 * 3) -> str:
    return (datetime.now() - timedelta(days=random.randint(0, within_days))).date().isoformat()


def make_donors():
    donors = []
    for i in range(N_DONORS):
        fn, ln = random.choice(FIRST), random.choice(LAST)
        city, state, zipc = random.choice(CITIES)
        created = rand_dt(900)
        updated = created + timedelta(days=random.randint(0, 200), hours=random.randint(0, 23))

        rel_type = random.choices(REL_TYPES, weights=REL_WEIGHTS, k=1)[0]
        org = random.choice(ORGS)
        interests = ", ".join(random.sample(INTEREST_POOL, k=random.randint(1, 3)))

        donors.append((
            uid(),                                   # DonorID
            f"{fn} {ln}",                             # FullName
            f"{fn.lower()}.{ln.lower()}{i}@example.com",
            f"+1{random.randint(2000000000, 9999999999)}",
            random.choice(PREF),                      # PreferredContactMethod
            f"{random.randint(100, 9999)} {random.choice(['Market','Castro','Main','El Camino','University'])} St",
            random.choice(["", "Apt 1", "Apt 22", "Suite 300"]),
            zipc, city, state, "US",
            rand_date(),                              # ActiveSinceDate
            fmt_dt(created),                          # CreatedAt
            fmt_dt(updated),                          # UpdatedAt
            rel_type,                                 # RelationshipType
            org,                                      # Organization
            interests,                                # Interests
            "NOT_STARTED",                            # FollowUpStatus
            None, None, 0.0, 0.0, 0, None, None, 0.0  # rollup fields
        ))
    return donors


def make_activities():
    acts = []
    for i in range(N_ACTIVITIES):
        # Some activities may not have fixed time
        if random.random() < 0.12:
            start = end = None
        else:
            start = rand_dt(240)
            end = start + timedelta(hours=random.randint(1, 4), minutes=random.randint(0, 45))

        acts.append((
            uid(),  # ActivityID
            f"Activity {i+1}: {random.choice(['Gala','Meetup','Volunteer Day','Regular Concert','Free Concert', 'Fundraising Event'])}",
            random.choice([
                "Community gathering and updates.",
                "N/A",
            ]),
            fmt_dt(start),
            fmt_dt(end),
            float(round(random.choice([0, 10, 25, 50, 100, 250]), 2)),  # ListPrice
            "USD",
            fmt_dt(datetime.now()),
        ))
    return acts


def make_donor_activity(donor_ids, activities):
    # Map ActivityID -> start time (string)
    a_start = {a[0]: a[3] for a in activities}

    rows = []
    for did in donor_ids:
        k = random.randint(0, MAX_ENGAGEMENTS_PER_DONOR)
        if k == 0:
            continue

        chosen = random.sample([a[0] for a in activities], k=min(k, len(activities)))
        for aid in chosen:
            start_str = a_start.get(aid)

            # Create REGISTER engagement for many
            if random.random() < 0.65:
                if start_str:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    engaged_at = start_dt - timedelta(days=random.randint(0, 25), hours=random.randint(0, 23))
                else:
                    engaged_at = rand_dt(240)

                rows.append((
                    uid(), did, aid,
                    random.choices(["CUSTOMER","AUDIENCE"], weights=[70, 30], k=1)[0],  # role
                    "REGISTER",
                    random.choices(["PLANNED","COMPLETED","CANCELLED"], weights=[55, 35, 10], k=1)[0],
                    fmt_dt(engaged_at),
                    None,
                    ""
                ))

            # Create ATTEND engagement for some
            if random.random() < 0.45:
                if start_str:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    engaged_at = start_dt - timedelta(days=random.randint(0, 25), hours=random.randint(0, 23))
                    participate = start_dt + timedelta(minutes=random.randint(-10, 60))
                else:
                    engaged_at = rand_dt(240)
                    participate = engaged_at + timedelta(days=random.randint(0, 10), minutes=random.randint(0, 120))

                status = random.choices(["COMPLETED","NO_SHOW","CANCELLED"], weights=[80, 15, 5], k=1)[0]
                participate_val = participate if status == "COMPLETED" else None

                rows.append((
                    uid(), did, aid,
                    random.choices(["AUDIENCE","CUSTOMER"], weights=[55, 45], k=1)[0],
                    "ATTEND",
                    status,
                    fmt_dt(engaged_at),
                    fmt_dt(participate_val),
                    ""
                ))

            # VOLUNTEER engagement for few
            if random.random() < 0.12:
                engaged_at = rand_dt(365)
                rows.append((
                    uid(), did, aid,
                    "VOLUNTEER",
                    "VOLUNTEER",
                    random.choices(["PLANNED","COMPLETED","CANCELLED"], weights=[40, 50, 10], k=1)[0],
                    fmt_dt(engaged_at),
                    None,
                    "Volunteered for event"
                ))

    return rows


def infer_item(tx_type: str):
    if tx_type == "DONATION":
        return ("Donation / DONATION_GENERAL", 1)
    if tx_type == "TICKET":
        return (random.choice(["Gala Ticket / TICKET_GALA", "Meetup Ticket / TICKET_MEETUP"]), 0)
    if tx_type == "MERCH":
        return (random.choice(["T-Shirt / MERCH_SHIRT", "Mug / MERCH_MUG", "Sticker Pack / MERCH_STICKERS"]), 0)
    if tx_type == "FEE":
        return ("Membership Fee / FEE_MEMBERSHIP", 0)
    return ("Other Purchase / OTHER_MISC", 0)


def make_transactions(donor_ids, activity_ids):
    rows = []
    for did in donor_ids:
        # Random number of transactions per donor (some donors have none)
        k = max(0, int(round(random.random() * AVG_TX_PER_DONOR * 2)))
        for _ in range(k):
            tx_type = random.choices(TX_TYPE, weights=[45, 20, 18, 10, 7], k=1)[0]
            item, is_tax = infer_item(tx_type)

            # Link some transactions to activities (tickets/fees more likely)
            if tx_type in ("TICKET", "FEE"):
                aid = random.choice(activity_ids) if activity_ids and random.random() < 0.85 else None
            elif tx_type == "DONATION":
                aid = random.choice(activity_ids) if activity_ids and random.random() < 0.25 else None
            else:
                aid = random.choice(activity_ids) if activity_ids and random.random() < 0.15 else None

            tx_dt = rand_dt(365)
            qty = random.randint(1, 4) if tx_type in ("TICKET", "MERCH") else 1

            if tx_type == "DONATION":
                price = random.choice([10, 25, 50, 100, 250, 500, 1000])
            elif tx_type == "TICKET":
                price = random.choice([25, 50, 100, 150, 250])
            elif tx_type == "MERCH":
                price = random.choice([5, 10, 20, 35, 50])
            elif tx_type == "FEE":
                price = random.choice([20, 40, 80, 120])
            else:
                price = random.choice([5, 15, 30, 60])

            amount = round(float(price) * qty, 2)

            pay_status = random.choices(PAY_STATUS, weights=[88, 8, 4], k=1)[0]
            pay_method = random.choice(PAY_METHOD)
            receipt_sent = 1 if random.random() < 0.6 else 0

            rows.append((
                uid(), did, aid, fmt_dt(tx_dt),
                qty, float(price), float(amount), "USD",
                tx_type, item, pay_method, pay_status,
                receipt_sent, is_tax
            ))
    return rows


def apply_rollups(conn: sqlite3.Connection):
    # TotalTransactionAmount (SUCCESS)
    conn.execute("""
      UPDATE Donor
      SET TotalTransactionAmount = (
        SELECT COALESCE(SUM(t.TransactionAmount), 0)
        FROM "Transaction" t
        WHERE t.DonorID = Donor.DonorID AND t.PaymentStatus='SUCCESS'
      )
    """)

    # TotalDonated + LastDonationAt (SUCCESS + DONATION)
    conn.execute("""
      UPDATE Donor
      SET TotalDonated = (
        SELECT COALESCE(SUM(t.TransactionAmount), 0)
        FROM "Transaction" t
        WHERE t.DonorID = Donor.DonorID
          AND t.PaymentStatus='SUCCESS'
          AND t.TransactionType='DONATION'
      ),
      LastDonationAt = (
        SELECT MAX(t.TransactionDateTime)
        FROM "Transaction" t
        WHERE t.DonorID = Donor.DonorID
          AND t.PaymentStatus='SUCCESS'
          AND t.TransactionType='DONATION'
      )
    """)

    # LastActivityAt (COMPLETED)
    conn.execute("""
      UPDATE Donor
      SET LastActivityAt = (
        SELECT MAX(COALESCE(da.ParticipateStartAt, da.EngagedAt))
        FROM DonorActivity da
        WHERE da.DonorID = Donor.DonorID
          AND da.EngagementStatus='COMPLETED'
      )
    """)

    # Simple Status/Tier rules
    now = datetime.now()
    donors = conn.execute("SELECT DonorID, LastDonationAt, LastActivityAt, TotalDonated FROM Donor").fetchall()

    for did, last_don, last_act, total_don in donors:
        candidates = []
        for s in (last_don, last_act):
            if s:
                candidates.append(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))

        if not candidates:
            status = "NEW"
        else:
            last = max(candidates)
            days = (now - last).days
            status = "ACTIVE" if days <= 30 else ("WARM" if days <= 120 else "LAPSED")

        td = float(total_don or 0)
        tier = "PLATINUM" if td >= 2000 else ("GOLD" if td >= 500 else ("SILVER" if td >= 100 else "BRONZE"))

        eng_count = conn.execute(
            "SELECT COUNT(*) FROM DonorActivity WHERE DonorID=? AND EngagementStatus='COMPLETED'", (did,)
        ).fetchone()[0]

        tier_pts = {"BRONZE": 5, "SILVER": 20, "GOLD": 35, "PLATINUM": 40}.get(tier, 0)
        recency_pts = max(0, 30 - int((now - max(candidates)).days / 5)) if candidates else 0
        eng_pts = min(30, eng_count * 6)
        priority = round(tier_pts + recency_pts + eng_pts, 1)

        conn.execute(
            "UPDATE Donor SET Status=?, Tier=?, EngagementCount=?, PriorityScore=? WHERE DonorID=?",
            (status, tier, eng_count, priority, did)
        )


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run init_db.py first.")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Clear existing data (safe for repeated runs)
    conn.execute('DELETE FROM "Transaction";')
    conn.execute("DELETE FROM DonorActivity;")
    conn.execute("DELETE FROM Activity;")
    conn.execute("DELETE FROM Donor;")

    donors = make_donors()
    activities = make_activities()

    donor_ids = [d[0] for d in donors]
    activity_ids = [a[0] for a in activities]

    donor_activity = make_donor_activity(donor_ids, activities)
    transactions = make_transactions(donor_ids, activity_ids)

    conn.executemany("""
      INSERT INTO Donor (
        DonorID, FullName, Email, PhoneNumber, PreferredContactMethod,
        AddressLine1, AddressLine2, ZipCode, City, State, Country,
        ActiveSinceDate, CreatedAt, UpdatedAt,
        RelationshipType, Organization, Interests, FollowUpStatus,
        LastDonationAt, LastActivityAt, TotalDonated, TotalTransactionAmount,
        EngagementCount, Status, Tier, PriorityScore
      ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, donors)

    conn.executemany("""
      INSERT INTO Activity (
        ActivityID, ActivityName, ActivityDetails, ActivityStartTime, ActivityEndTime,
        ListPrice, Currency, ActivityCreatedAt
      ) VALUES (?,?,?,?,?,?,?,?)
    """, activities)

    conn.executemany("""
      INSERT INTO DonorActivity (
        DonorActivityID, DonorID, ActivityID,
        EngagementRole, EngagementType, EngagementStatus,
        EngagedAt, ParticipateStartAt, Notes
      ) VALUES (?,?,?,?,?,?,?,?,?)
    """, donor_activity)

    conn.executemany("""
      INSERT INTO "Transaction" (
        TransactionID, DonorID, ActivityID, TransactionDateTime,
        Quantity, TransactionPrice, TransactionAmount, Currency,
        TransactionType, TransactionItem, PaymentMethod, PaymentStatus,
        ReceiptSent, IsTaxDeductible
      ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, transactions)

    apply_rollups(conn)
    conn.commit()

    counts = {
        "Donor": conn.execute("SELECT COUNT(*) FROM Donor").fetchone()[0],
        "Activity": conn.execute("SELECT COUNT(*) FROM Activity").fetchone()[0],
        "DonorActivity": conn.execute("SELECT COUNT(*) FROM DonorActivity").fetchone()[0],
        "Transaction": conn.execute('SELECT COUNT(*) FROM "Transaction"').fetchone()[0],
    }
    print("✅ Seed complete:", counts)

    conn.close()


if __name__ == "__main__":
    main()