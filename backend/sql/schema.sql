PRAGMA foreign_keys = ON;

-- =========================
-- Donor
-- =========================
CREATE TABLE IF NOT EXISTS Donor (
  DonorID TEXT PRIMARY KEY,                           -- UUID stored as TEXT in SQLite
  FullName TEXT,
  Email TEXT,
  PhoneNumber TEXT,

  PreferredContactMethod TEXT DEFAULT 'EMAIL'
    CHECK (PreferredContactMethod IN ('EMAIL','PHONE','SMS','NONE')),

  AddressLine1 TEXT,
  AddressLine2 TEXT,
  ZipCode TEXT,
  City TEXT,
  State TEXT,
  Country TEXT DEFAULT 'US'
    CHECK (length(Country) = 2),

  ActiveSinceDate TEXT,                               -- DATE stored as 'YYYY-MM-DD'
  CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),   -- TIMESTAMP stored as text
  UpdatedAt TEXT NOT NULL DEFAULT (datetime('now')),

  -- Profile enrichment
  RelationshipType TEXT DEFAULT 'PROSPECT'
    CHECK (RelationshipType IN ('DONOR','VOLUNTEER','SPONSOR','PROSPECT') OR RelationshipType IS NULL),
  Organization TEXT,
  Interests TEXT,                                      -- comma-separated tags

  -- Follow-up workflow
  FollowUpStatus TEXT NOT NULL DEFAULT 'NOT_STARTED'
    CHECK (FollowUpStatus IN ('NOT_STARTED','PLANNED','COMPLETED')),

  -- Derived/cached rollups
  LastDonationAt TEXT,
  LastActivityAt TEXT,
  TotalDonated REAL DEFAULT 0,
  TotalTransactionAmount REAL DEFAULT 0,
  EngagementCount INTEGER DEFAULT 0,
  Status TEXT CHECK (Status IN ('NEW','ACTIVE','WARM','LAPSED') OR Status IS NULL),
  StatusOverride TEXT CHECK (StatusOverride IN ('NEW','ACTIVE','WARM','LAPSED') OR StatusOverride IS NULL),
  Tier TEXT CHECK (Tier IN ('BRONZE','SILVER','GOLD','PLATINUM') OR Tier IS NULL),
  PriorityScore REAL DEFAULT 0
);

-- Optional: enforce unique emails if you want (comment out if not)
-- CREATE UNIQUE INDEX IF NOT EXISTS ux_donor_email ON Donor(Email);

CREATE INDEX IF NOT EXISTS idx_donor_city_state ON Donor(City, State);


-- =========================
-- Activity
-- =========================
CREATE TABLE IF NOT EXISTS Activity (
  ActivityID TEXT PRIMARY KEY,                         -- UUID as TEXT
  ActivityName TEXT NOT NULL,
  ActivityDetails TEXT,
  ActivityStartTime TEXT,                              -- TIMESTAMP as text
  ActivityEndTime TEXT,                                -- TIMESTAMP as text
  ListPrice REAL NOT NULL DEFAULT 0,
  Currency TEXT NOT NULL DEFAULT 'USD'
    CHECK (length(Currency) = 3),
  ActivityCreatedAt TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_activity_start_time ON Activity(ActivityStartTime);


-- =========================
-- DonorActivity (engagement events)
-- =========================
CREATE TABLE IF NOT EXISTS DonorActivity (
  DonorActivityID TEXT PRIMARY KEY,                    -- UUID as TEXT
  DonorID TEXT NOT NULL,
  ActivityID TEXT NOT NULL,

  EngagementRole TEXT NOT NULL DEFAULT 'CUSTOMER'
    CHECK (EngagementRole IN ('AUDIENCE','VOLUNTEER','CUSTOMER','STAFF')),

  EngagementType TEXT NOT NULL
    CHECK (EngagementType IN ('REGISTER','ATTEND','VOLUNTEER')),

  EngagementStatus TEXT NOT NULL DEFAULT 'PLANNED'
    CHECK (EngagementStatus IN ('PLANNED','COMPLETED','CANCELLED','NO_SHOW')),

  EngagedAt TEXT,                                      -- e.g., registration timestamp
  ParticipateStartAt TEXT,                             -- actual attendance start (timepoint)
  Notes TEXT,

  FOREIGN KEY (DonorID) REFERENCES Donor(DonorID) ON DELETE CASCADE,
  FOREIGN KEY (ActivityID) REFERENCES Activity(ActivityID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_donor_activity_donor ON DonorActivity(DonorID);
CREATE INDEX IF NOT EXISTS idx_donor_activity_activity ON DonorActivity(ActivityID);
CREATE INDEX IF NOT EXISTS idx_donor_activity_type_status ON DonorActivity(EngagementType, EngagementStatus);

-- =========================

-- =========================
-- Transaction (money events)
-- =========================
CREATE TABLE IF NOT EXISTS "Transaction" (
  TransactionID TEXT PRIMARY KEY,                      -- UUID as TEXT
  DonorID TEXT NOT NULL,
  ActivityID TEXT,                                     -- nullable FK
  TransactionDateTime TEXT NOT NULL,                   -- TIMESTAMP as text

  Quantity INTEGER NOT NULL DEFAULT 1,
  TransactionPrice REAL NOT NULL,                      -- unit price
  TransactionAmount REAL NOT NULL,                     -- price * qty (or donation amount)

  Currency TEXT NOT NULL DEFAULT 'USD'
    CHECK (length(Currency) = 3),

  TransactionType TEXT NOT NULL
    CHECK (TransactionType IN ('DONATION','TICKET','MERCH','FEE','OTHER')),

  TransactionItem TEXT,                                -- Item name / SKU

  PaymentMethod TEXT NOT NULL,
  PaymentStatus TEXT NOT NULL
    CHECK (PaymentStatus IN ('SUCCESS','FAIL','REFUNDED')),

  ReceiptSent INTEGER NOT NULL DEFAULT 0
    CHECK (ReceiptSent IN (0,1)),

  IsTaxDeductible INTEGER NOT NULL DEFAULT 0
    CHECK (IsTaxDeductible IN (0,1)),

  FOREIGN KEY (DonorID) REFERENCES Donor(DonorID) ON DELETE CASCADE,
  FOREIGN KEY (ActivityID) REFERENCES Activity(ActivityID) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_donor ON "Transaction"(DonorID);
CREATE INDEX IF NOT EXISTS idx_tx_activity ON "Transaction"(ActivityID);
CREATE INDEX IF NOT EXISTS idx_tx_type_status ON "Transaction"(TransactionType, PaymentStatus);


-- =========================
-- Touchpoint (staff call/email notes)
-- =========================
CREATE TABLE IF NOT EXISTS Touchpoint (
  TouchpointID TEXT PRIMARY KEY,                        -- UUID as TEXT
  DonorID TEXT NOT NULL,
  Note TEXT NOT NULL,
  CreatedAt TEXT NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (DonorID) REFERENCES Donor(DonorID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_touchpoint_donor ON Touchpoint(DonorID);