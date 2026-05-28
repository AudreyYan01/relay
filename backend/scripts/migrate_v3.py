"""
Migration v3: adds RecommendationLog table for the suggestion-disposition loop.

Run once against your existing database:
    cd backend
    python scripts/migrate_v3.py
"""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "app.db"


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS RecommendationLog (
            LogID       TEXT PRIMARY KEY,
            DonorID     TEXT NOT NULL,
            SuggestedAction TEXT NOT NULL,
            ActionType  TEXT NOT NULL,
            RuleVersion TEXT NOT NULL DEFAULT 'v1',
            InputSnapshot TEXT,
            Disposition TEXT CHECK (
                Disposition IN ('accepted', 'edited', 'dismissed', 'deferred')
                OR Disposition IS NULL
            ),
            Rationale   TEXT,
            EditedAction TEXT,
            CreatedAt   TEXT NOT NULL DEFAULT (datetime('now')),
            DisposedAt  TEXT,
            FOREIGN KEY (DonorID) REFERENCES Donor(DonorID) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reclog_donor ON RecommendationLog(DonorID, CreatedAt)"
    )
    conn.commit()
    print("✅ Migration v3 complete: RecommendationLog table ready")


if __name__ == "__main__":
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run init_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate(conn)
    conn.close()
