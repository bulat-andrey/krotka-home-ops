import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/krotka.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _rebuild_zones_without_name_unique(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'zones'"
    ).fetchone()
    if not row or "name TEXT NOT NULL UNIQUE" not in row["sql"]:
        return
    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        CREATE TABLE zones_rebuild (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT NOT NULL,
            type TEXT,
            sun_exposure TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO zones_rebuild (id, code, name, type, sun_exposure, notes, active)
        SELECT id, code, name, type, sun_exposure, notes, active FROM zones;
        DROP TABLE zones;
        ALTER TABLE zones_rebuild RENAME TO zones;
        PRAGMA foreign_keys=ON;
    """)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            name TEXT NOT NULL,
            type TEXT,
            sun_exposure TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS watering_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER NOT NULL REFERENCES zones(id),
            date TEXT NOT NULL,
            duration_min INTEGER,
            method TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS weather_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            temp_max REAL,
            temp_min REAL,
            rain_mm REAL,
            forecast_rain_mm REAL,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS wind_hourly (
            ts TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            wind_speed_kt REAL,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id INTEGER NOT NULL REFERENCES zones(id),
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT
        );

        CREATE TABLE IF NOT EXISTS contractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS mowing_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            contractor_id INTEGER REFERENCES contractors(id),
            quality INTEGER,
            notes TEXT,
            photos TEXT
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            contractor_id INTEGER REFERENCES contractors(id),
            status TEXT NOT NULL DEFAULT 'draft',
            sent_at TEXT,
            due_at TEXT,
            last_response_at TEXT,
            summary TEXT,
            next_action TEXT
        );

        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER REFERENCES requests(id),
            direction TEXT NOT NULL,
            sender TEXT,
            recipient TEXT,
            subject TEXT,
            body TEXT,
            sent_at TEXT,
            attachments TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT,
            title TEXT,
            description TEXT,
            zone_id INTEGER REFERENCES zones(id),
            contractor_id INTEGER REFERENCES contractors(id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    _ensure_column(conn, "zones", "code", "TEXT")
    _ensure_column(conn, "zones", "notes", "TEXT")
    _ensure_column(conn, "zones", "active", "INTEGER NOT NULL DEFAULT 1")
    _rebuild_zones_without_name_unique(conn)
    _ensure_column(conn, "requests", "deleted_at", "TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_zones_code ON zones(code) WHERE code IS NOT NULL AND code != ''"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wind_hourly_date ON wind_hourly(date)")

    # Seed zones
    zones = [
        ("газон", "lawn", "sun"),
        ("самшиты", "bushes", "partial"),
        ("новые посадки", "new_plants", "mixed"),
        ("тень", "shade_area", "shade"),
        ("солнце", "sun_area", "sun"),
    ]
    for name, type_, sun in zones:
        existing = conn.execute(
            "SELECT id FROM zones WHERE name = ? AND type = ? LIMIT 1",
            (name, type_),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO zones (name, type, sun_exposure) VALUES (?, ?, ?)",
                (name, type_, sun),
            )

    # Seed contractors
    for name in ("Dawid", "Mateusz", "Bartek", "Gestia"):
        conn.execute("INSERT OR IGNORE INTO contractors (name) VALUES (?)", (name,))

    conn.commit()
    conn.close()
