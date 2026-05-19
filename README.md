# Relay — Lifecycle & Engagement System for Relationship-Driven Organizations

A full-stack decision-support tool for teams that run on relationships. Helps program staff review supporter relationships after an event, identify who needs follow-up, and decide what action to take next.

---

## Why this exists

Relationship-driven organizations — arts groups, community programs, civic organizations, membership associations — face a resource allocation problem. Engagement capacity is finite: staff time, personal outreach, event invitations. But decisions about where to invest that capacity are typically made from intuition, stale spreadsheets, or whoever sent the last email.

The result is systematic misallocation: over-investment in the obvious, under-investment in the mid-tier relationships that represent the highest growth potential.

Relay doesn't automate those decisions. It makes them easier to make well — by surfacing the right signals at the right moment, generating a plain-language relationship brief for each supporter, and tracking follow-up so nothing falls through.

Relay is intentionally lightweight. It is built for small teams — one to a handful of people managing a few hundred relationships — not enterprise CRMs with complex permissions, workflows, and integrations. The goal is low friction: open the app, see what needs attention, act.

**The core user story:**
> The team just hosted an event. A program lead opens the dashboard, sees who attended, identifies which relationships need attention, reads a brief on each one, decides on a next action, and logs it — all in one sitting.

---

## What's built (v0.1 scope)

| Feature | What it does |
|---|---|
| Dashboard | Summary cards (total supporters, total giving, follow-up queue, high-priority count), top supporters by giving, recent donation feed |
| Supporter List | Browse all relationships with status and type filters, name search, export to CSV |
| Supporter Profile | Full contact info, giving history, engagement timeline, staff notes |
| Relationship Brief | Rule-based summary: who they are, why they matter, recent signal, risk or opportunity flag |
| Suggested Next Action | Specific outreach recommendation based on status, tier, and relationship type |
| Follow-Up Workflow | Three-state status (Not Started → Planned → Completed), persisted to database |
| Events | Activity log with attendee count and revenue per event |

Not in scope: authentication, real payments, CRM import, email integration, live AI.

---

## Design choices

### Why FastAPI + SQLite, not Django or a managed database

FastAPI is Python, typed, and generates interactive API docs automatically at `/docs` — useful for understanding every endpoint during development. For a local MVP with one user and a few hundred supporters, SQLite is more than sufficient and has zero ops overhead. The schema is designed to migrate cleanly to PostgreSQL if this needed to scale.

### Why the relationship brief is rule-based

The brief logic in `backend/services/brief.py` uses engagement status, giving tier, activity count, and recency to generate relationship summaries. No API key, no latency, no cost, no hallucinations. The output is deterministic, which makes it debuggable and easy to explain. The data model and brief interface are designed so a real language model could replace the rule engine later with no frontend changes.

### Why priority score is a formula, not a ranking

`PriorityScore = Tier pts (max 40) + Recency pts (max 30) + Engagement depth pts (max 30)`

A numeric score makes the ranking transparent and adjustable. Staff can see *why* someone ranks #1 vs #3. The weights reflect a deliberate product judgment: giving history matters most, but a deeply engaged non-donor should still surface above a lapsed major contributor.

### Why rollups are cached on the Supporter row

Fields like `TotalDonated`, `Status`, and `PriorityScore` are pre-computed and stored directly on the `Donor` table rather than recalculated on every request. This keeps list queries fast (no joins or aggregations at read time) and the API response shape simple. The tradeoff: rollups only recompute when a transaction is posted, so status can drift between updates.

### Why follow-up is a three-state field, not a task system

A full task system (due dates, assignees, reminders) is the right answer for a large team. For a small program operation, the overhead of maintaining tasks creates friction that kills adoption. A simple NOT_STARTED → PLANNED → COMPLETED toggle covers 90% of the workflow at 10% of the complexity.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, JavaScript, plain CSS |
| Backend | FastAPI (Python 3.10+) |
| Database | SQLite |
| API style | REST — JSON over HTTP |
| Brief generation | Rule-based (no external AI dependency) |

---

## Project structure

```
Relay/
│
├── backend/
│   ├── main.py                 # All FastAPI routes (11 endpoints)
│   ├── services/
│   │   ├── rollups.py          # Recomputes Status, Tier, PriorityScore per supporter
│   │   └── brief.py           # Rule-based relationship brief generator
│   ├── sql/
│   │   └── schema.sql          # 5 tables: Donor, Activity, DonorActivity, Transaction, Touchpoint
│   ├── scripts/
│   │   ├── init_db.py          # Creates the database from schema.sql
│   │   └── seed_data.py        # Generates 50 supporters, 18 events, ~120 transactions
│   ├── data/
│   │   └── app.db              # SQLite database (generated — not in version control)
│   └── requirements.txt
│
└── donor-management-mvp/
    ├── src/
    │   ├── App.js              # React Router setup, nav bar
    │   ├── App.css             # All styles (no framework)
    │   ├── api/
    │   │   └── client.js       # Thin fetch wrapper — one method per endpoint
    │   └── pages/
    │       ├── Dashboard.js    # Summary cards, top supporters table, recent giving feed
    │       ├── SupporterList.js # Filterable table, CSV export
    │       ├── SupporterProfile.js # Profile, brief panel, follow-up, note logger
    │       └── Events.js       # Activity log with attendance and revenue
    └── package.json
```

---

## Running locally

### Prerequisites

- Python 3.10 or later
- Node.js 18 or later

---

### Step 1 — Start the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Build the database and load demo data
python scripts/init_db.py       # creates app.db from schema.sql
python scripts/seed_data.py     # seeds 50 supporters, 18 events, 120+ transactions

# Start the API server
uvicorn main:app --reload --port 8000
```

The API is now running at **http://localhost:8000**

Interactive API docs (all routes, try them in the browser): **http://localhost:8000/docs**

---

### Step 2 — Start the frontend

Open a second terminal window:

```bash
cd donor-management-mvp

npm install
npm start
```

The app opens at **http://localhost:3000**

Both terminals must stay running. The frontend calls the backend at port 8000.

---

### If you change the schema

Re-run both scripts to rebuild from scratch:

```bash
cd backend
python scripts/init_db.py    # drops and recreates all tables
python scripts/seed_data.py  # reloads all seed data
```

Safe to run repeatedly — `seed_data.py` clears all tables before inserting.

---

## Data model

```
Donor           core identity, contact info, cached rollup fields
Activity        events the org runs (concerts, galas, volunteer days, meetups)
DonorActivity   who participated in which event, in what role, with what outcome
Transaction     financial records (donations, tickets, merchandise, fees)
Touchpoint      staff notes logged directly from the relationship profile
```

**Computed fields on Donor** — recalculated whenever a transaction is posted:

| Field | Logic |
|---|---|
| `TotalDonated` | Sum of successful DONATION-type transactions |
| `TotalTransactionAmount` | Sum of all successful transactions (tickets, merch, etc.) |
| `LastDonationAt` | Most recent successful donation timestamp |
| `LastActivityAt` | Most recent completed engagement timestamp |
| `Status` | Recency: ≤30 days → ACTIVE · ≤120 days → WARM · older → LAPSED |
| `Tier` | Lifetime giving: <$100 BRONZE · $100 SILVER · $500 GOLD · $2,000+ PLATINUM |
| `PriorityScore` | Tier pts (max 40) + Recency pts (max 30) + Engagement pts (max 30) |

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/dashboard` | Summary stats, top 10 supporters by giving, 8 most recent donations |
| GET | `/donors` | All supporters — filter by `status`, `relationship_type`, `search` |
| GET | `/donors/:id` | Full profile: supporter, transactions, engagements, touchpoints |
| GET | `/donors/:id/brief` | Rule-based relationship brief and suggested next action |
| PATCH | `/donors/:id/followup` | Update follow-up status (NOT_STARTED / PLANNED / COMPLETED) |
| PATCH | `/donors/:id/status` | Manually override computed status (pass null to revert to auto) |
| POST | `/donors/:id/touchpoints` | Log a staff note — appended to the engagement timeline |
| GET | `/events` | All activities with attendee count and revenue totals |
| POST | `/donors` | Create a supporter, or return existing if email/phone matches |
| POST | `/transactions` | Record a financial transaction and recompute supporter rollups |

---

## Known limitations

Relay is designed for small teams, not enterprise scale. These are intentional constraints, not bugs:

- **No authentication.** Single-user, local-only. Not designed for shared cloud access.
- **No concurrent writes.** SQLite handles one writer at a time — fine for a small team, wrong tool for multi-user production.
- **Rollups go stale.** Status and PriorityScore only update when a new transaction is posted — not when time passes or when an engagement is logged.
- **No pagination.** The supporter list is capped at 100 results.
- **Brief is rule-based.** The relationship summary won't surface nuance that isn't already in the structured data.
