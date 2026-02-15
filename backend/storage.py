import os
import sqlite3

BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DB_DIR, 'cardio.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
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
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()]
        if "details_json" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN details_json TEXT")
            conn.commit()
        if "owner_user_id" not in cols:
            conn.execute("ALTER TABLE profiles ADD COLUMN owner_user_id TEXT")
            conn.commit()
        note_cols = [r["name"] for r in conn.execute("PRAGMA table_info(doctor_notes)").fetchall()]
        if "ecg_signal_json" not in note_cols:
            conn.execute("ALTER TABLE doctor_notes ADD COLUMN ecg_signal_json TEXT")
            conn.commit()
    finally:
        conn.close()
