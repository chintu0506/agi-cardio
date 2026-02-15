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


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_db_dir = storage.DB_DIR
        cls._orig_db_path = storage.DB_PATH
        cls._orig_upload_dir = storage.UPLOAD_DIR
        cls._tmp = tempfile.TemporaryDirectory()
        storage.DB_DIR = cls._tmp.name
        storage.DB_PATH = os.path.join(cls._tmp.name, "cardio_test_validation.db")
        storage.UPLOAD_DIR = os.path.join(cls._tmp.name, "uploads")
        os.makedirs(storage.UPLOAD_DIR, exist_ok=True)
        storage.init_db()

    @classmethod
    def tearDownClass(cls):
        storage.DB_DIR = cls._orig_db_dir
        storage.DB_PATH = cls._orig_db_path
        storage.UPLOAD_DIR = cls._orig_upload_dir
        cls._tmp.cleanup()

    def setUp(self):
        SESSIONS.clear()
        conn = storage.get_db()
        try:
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
        email = "validation.patient@example.com"
        password = "pass1234"
        initiate = self.client.post(
            "/api/auth/signup/initiate",
            json={"name": "Validation Patient", "email": email, "password": password, "role": "patient"},
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
        return login.get_json()["token"]

    def test_predict_rejects_unknown_fields(self):
        payload = dict(DEFAULT_PATIENT)
        payload["unexpected_field"] = 1
        r = self.client.post("/api/predict", json=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unknown fields", r.get_json().get("error", ""))

    def test_predict_rejects_out_of_range_values(self):
        payload = dict(DEFAULT_PATIENT)
        payload["age"] = 200
        r = self.client.post("/api/predict", json=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Age (yrs) must be <=", r.get_json().get("error", ""))

    def test_predict_rejects_invalid_category(self):
        payload = dict(DEFAULT_PATIENT)
        payload["sex"] = 9
        r = self.client.post("/api/predict", json=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Sex must be one of", r.get_json().get("error", ""))

    def test_profile_creation_rejects_invalid_age(self):
        token = self._login_patient()
        r = self.client.post(
            "/api/profiles",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"full_name": "Bad Age", "age": 0, "details": {}},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("age must be between 1 and 120", r.get_json().get("error", ""))


if __name__ == "__main__":
    unittest.main()
