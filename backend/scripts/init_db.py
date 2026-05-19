import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]   # backend/
DB_PATH = BASE_DIR / "data" / "app.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    conn.commit()
    conn.close()

    print(f"✅ Database created at: {DB_PATH}")

if __name__ == "__main__":
    main()