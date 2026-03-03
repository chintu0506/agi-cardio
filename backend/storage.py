import os
import sqlite3
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DATA_ROOT = os.getenv("AGI_DATA_DIR", BASE_DIR)
DB_DIR = os.getenv("AGI_DB_DIR", os.path.join(DATA_ROOT, "data"))
DB_PATH = os.getenv("AGI_DB_PATH", os.path.join(DB_DIR, "cardio.db"))
UPLOAD_DIR = os.getenv("AGI_UPLOAD_DIR", os.path.join(DATA_ROOT, "uploads"))
BACKUP_DIR = os.getenv("AGI_BACKUP_DIR", os.path.join(DATA_ROOT, "backups"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_cols(conn, table_name):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]


def _ensure_migration_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _run_migration(conn, name, fn):
    done = conn.execute("SELECT 1 FROM schema_migrations WHERE name = ?", (name,)).fetchone()
    if done:
        return
    fn(conn)
    conn.execute(
        "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
        (name, datetime.now().isoformat()),
    )
    conn.commit()


def _migrate_profiles_columns(conn):
    cols = _table_cols(conn, "profiles")
    if "details_json" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN details_json TEXT")
    if "owner_user_id" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN owner_user_id TEXT")


def _migrate_doctor_notes_ecg(conn):
    cols = _table_cols(conn, "doctor_notes")
    if "ecg_signal_json" not in cols:
        conn.execute("ALTER TABLE doctor_notes ADD COLUMN ecg_signal_json TEXT")


def _migrate_audit_log(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            status TEXT NOT NULL DEFAULT 'SUCCESS',
            payload_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id)")


def _migrate_core_indexes(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_owner ON profiles(owner_user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_profile_created ON diagnoses(profile_id, created_at)")


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    db_parent = os.path.dirname(DB_PATH)
    if db_parent:
        os.makedirs(db_parent, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                age INTEGER,
                sex INTEGER,
                owner_user_id TEXT,
                details_json TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diagnoses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                report_id TEXT NOT NULL,
                risk_level TEXT,
                master_probability REAL,
                input_payload TEXT NOT NULL,
                result_payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                mobile TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_user_id TEXT NOT NULL,
                uploaded_by_user_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                diagnosis_summary TEXT,
                upload_date TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_user_id TEXT NOT NULL,
                patient_user_id TEXT NOT NULL,
                prescription TEXT,
                remarks TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_user_id TEXT NOT NULL,
                patient_user_id TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL,
                consult_link TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_user_id TEXT NOT NULL,
                patient_user_id TEXT NOT NULL,
                sender_role TEXT NOT NULL,
                message_text TEXT NOT NULL,
                attachment_url TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS otp_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                otp_id TEXT NOT NULL UNIQUE,
                user_contact TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                purpose TEXT NOT NULL,
                user_id TEXT,
                name TEXT,
                email TEXT,
                mobile TEXT,
                role TEXT,
                password_hash TEXT,
                attempts_left INTEGER NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

        _ensure_migration_table(conn)
        _run_migration(conn, "20260215_profiles_columns", _migrate_profiles_columns)
        _run_migration(conn, "20260215_doctor_notes_ecg_signal", _migrate_doctor_notes_ecg)
        _run_migration(conn, "20260215_audit_log", _migrate_audit_log)
        _run_migration(conn, "20260215_core_indexes", _migrate_core_indexes)
    finally:
        conn.close()


def log_audit_event(conn, *, action, entity_type, user_id=None, entity_id=None, status="SUCCESS", payload=None):
    payload_json = None
    if payload is not None:
        payload_json = json.dumps(payload, ensure_ascii=True)
    conn.execute(
        """
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, status, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            str(action),
            str(entity_type),
            None if entity_id is None else str(entity_id),
            str(status or "SUCCESS"),
            payload_json,
            datetime.now().isoformat(),
        ),
    )


def backup_database(label="manual", max_backups=30):
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    safe_label = "".join(ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in str(label or "manual"))
    safe_label = safe_label[:40] or "manual"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"cardio_{safe_label}_{ts}.db")
    shutil.copy2(DB_PATH, dst)

    removed = []
    keep = max(1, int(max_backups))
    backups = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )
    for old in backups[keep:]:
        os.remove(old)
        removed.append(old)
    return {"backup_path": dst, "removed": removed}
