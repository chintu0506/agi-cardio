import os
import sys
import tempfile
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import storage  # noqa: E402
from app import DEFAULT_PATIENT, app  # noqa: E402
from auth_access import SESSIONS  # noqa: E402


class DataSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_db_dir = storage.DB_DIR
        cls._orig_db_path = storage.DB_PATH
        cls._orig_upload_dir = storage.UPLOAD_DIR
        cls._orig_backup_dir = storage.BACKUP_DIR
        cls._tmp = tempfile.TemporaryDirectory()
        storage.DB_DIR = cls._tmp.name
        storage.DB_PATH = os.path.join(cls._tmp.name, "cardio_safety.db")
        storage.UPLOAD_DIR = os.path.join(cls._tmp.name, "uploads")
        storage.BACKUP_DIR = os.path.join(cls._tmp.name, "backups")
        os.makedirs(storage.UPLOAD_DIR, exist_ok=True)
        os.makedirs(storage.BACKUP_DIR, exist_ok=True)
        storage.init_db()

    @classmethod
    def tearDownClass(cls):
        storage.DB_DIR = cls._orig_db_dir
        storage.DB_PATH = cls._orig_db_path
        storage.UPLOAD_DIR = cls._orig_upload_dir
        storage.BACKUP_DIR = cls._orig_backup_dir
        cls._tmp.cleanup()

    def setUp(self):
        SESSIONS.clear()
        conn = storage.get_db()
        try:
            conn.execute("DELETE FROM audit_log")
            conn.execute("DELETE FROM diagnoses")
            conn.execute("DELETE FROM profiles")
            conn.execute("DELETE FROM doctor_notes")
            conn.execute("DELETE FROM doctor_messages")
            conn.execute("DELETE FROM doctor_appointments")
            conn.execute("DELETE FROM patient_records")
            conn.execute("DELETE FROM otp_codes")
            conn.execute("DELETE FROM users")
            conn.commit()
        finally:
            conn.close()
        self.client = app.test_client()

    def _login_patient(self):
        email = "safety.patient@example.com"
        password = "pass1234"
        initiate = self.client.post(
            "/api/auth/signup/initiate",
            json={"name": "Safety Patient", "email": email, "password": password, "role": "patient"},
        )
        self.assertEqual(initiate.status_code, 200)
        payload = initiate.get_json()
        otp_id = payload["otp_id"]
        otp_code = payload.get("otp_preview")
        if not otp_code:
            conn = storage.get_db()
            try:
                row = conn.execute("SELECT otp_code FROM otp_codes WHERE otp_id = ?", (otp_id,)).fetchone()
                otp_code = row["otp_code"]
            finally:
                conn.close()
        verify = self.client.post("/api/auth/signup/verify", json={"otp_id": otp_id, "otp_code": otp_code})
        self.assertEqual(verify.status_code, 201)
        login = self.client.post("/api/auth/login", json={"login": email, "password": password})
        self.assertEqual(login.status_code, 200)
        return login.get_json()["token"], verify.get_json()["user"]["user_id"]

    def test_migration_table_and_audit_table_exist(self):
        conn = storage.get_db()
        try:
            migrations = [r["name"] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall()]
            self.assertIn("20260215_audit_log", migrations)
            self.assertIn("20260215_core_indexes", migrations)
            self.assertIn("20260215_doctor_notes_ecg_signal", migrations)
            self.assertIn("20260215_profiles_columns", migrations)
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
            self.assertIn("action", cols)
            self.assertIn("entity_type", cols)
        finally:
            conn.close()

    def test_backup_database_rotation(self):
        one = storage.backup_database(label="test", max_backups=1)
        self.assertTrue(os.path.exists(one["backup_path"]))
        two = storage.backup_database(label="test", max_backups=1)
        self.assertTrue(os.path.exists(two["backup_path"]))
        backups = [f for f in os.listdir(storage.BACKUP_DIR) if f.endswith(".db")]
        self.assertEqual(len(backups), 1)

    def test_audit_trail_written_for_profile_and_diagnosis(self):
        token, user_id = self._login_patient()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        p = self.client.post(
            "/api/profiles",
            headers=headers,
            json={"full_name": "Safety Profile", "age": 55, "sex": 1, "details": {}},
        )
        self.assertEqual(p.status_code, 201)
        profile_id = p.get_json()["id"]
        d = self.client.post(
            f"/api/profiles/{profile_id}/diagnose",
            headers=headers,
            json=dict(DEFAULT_PATIENT),
        )
        self.assertEqual(d.status_code, 200)

        conn = storage.get_db()
        try:
            rows = conn.execute(
                "SELECT user_id, action, entity_type FROM audit_log ORDER BY id ASC"
            ).fetchall()
            actions = [r["action"] for r in rows]
            self.assertIn("CREATE_PROFILE", actions)
            self.assertIn("CREATE_DIAGNOSIS", actions)
            self.assertTrue(all(r["user_id"] == user_id for r in rows))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
