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


class PatientE2EFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_db_dir = storage.DB_DIR
        cls._orig_db_path = storage.DB_PATH
        cls._orig_upload_dir = storage.UPLOAD_DIR
        cls._tmp = tempfile.TemporaryDirectory()
        storage.DB_DIR = cls._tmp.name
        storage.DB_PATH = os.path.join(cls._tmp.name, "cardio_test.db")
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

    def _auth_headers(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _signup_verify_login(self, name, email, password, role):
        initiate = self.client.post(
            "/api/auth/signup/initiate",
            json={"name": name, "email": email, "password": password, "role": role},
        )
        self.assertEqual(initiate.status_code, 200, initiate.get_data(as_text=True))
        init_payload = initiate.get_json()
        otp_id = init_payload.get("otp_id")
        self.assertTrue(otp_id)

        otp_code = init_payload.get("otp_preview")
        if not otp_code:
            conn = storage.get_db()
            try:
                row = conn.execute(
                    "SELECT otp_code FROM otp_codes WHERE otp_id = ?",
                    (otp_id,),
                ).fetchone()
                self.assertIsNotNone(row)
                otp_code = row["otp_code"]
            finally:
                conn.close()

        verify = self.client.post(
            "/api/auth/signup/verify",
            json={"otp_id": otp_id, "otp_code": otp_code},
        )
        self.assertEqual(verify.status_code, 201, verify.get_data(as_text=True))
        verify_payload = verify.get_json()
        self.assertEqual(verify_payload["user"]["role"], role)

        login = self.client.post(
            "/api/auth/login",
            json={"login": email, "password": password},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        login_payload = login.get_json()
        self.assertTrue(login_payload.get("token"))
        return login_payload

    def test_patient_profile_diagnosis_history_workflow(self):
        login_payload = self._signup_verify_login(
            name="E2E Patient",
            email="patient.e2e@example.com",
            password="pass1234",
            role="patient",
        )
        token = login_payload["token"]
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["role"], "patient")

        create_profile = self.client.post(
            "/api/profiles",
            headers=self._auth_headers(token),
            json={
                "full_name": "Patient E2E Profile",
                "age": 56,
                "sex": 1,
                "notes": "profile for e2e workflow",
                "details": {"dob": "1970-01-01", "blood_group": "O+"},
            },
        )
        self.assertEqual(create_profile.status_code, 201, create_profile.get_data(as_text=True))
        profile = create_profile.get_json()
        profile_id = profile["id"]
        self.assertEqual(profile["full_name"], "Patient E2E Profile")

        list_profiles = self.client.get("/api/profiles", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(list_profiles.status_code, 200)
        profile_ids = [item["id"] for item in list_profiles.get_json()]
        self.assertIn(profile_id, profile_ids)

        diagnose = self.client.post(
            f"/api/profiles/{profile_id}/diagnose",
            headers=self._auth_headers(token),
            json=dict(DEFAULT_PATIENT),
        )
        self.assertEqual(diagnose.status_code, 200, diagnose.get_data(as_text=True))
        diagnosis_payload = diagnose.get_json()
        self.assertIn("report_id", diagnosis_payload)
        self.assertIn("master_probability", diagnosis_payload)
        self.assertIn("risk_tier", diagnosis_payload)
        self.assertIn("diseases", diagnosis_payload)

        history = self.client.get(
            f"/api/profiles/{profile_id}/diagnoses",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(history.status_code, 200)
        history_rows = history.get_json()
        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0]["profile_id"], profile_id)
        self.assertEqual(history_rows[0]["report_id"], diagnosis_payload["report_id"])
        self.assertIn("result_payload", history_rows[0])

    def test_profile_endpoints_require_auth(self):
        create_profile = self.client.post(
            "/api/profiles",
            json={"full_name": "NoAuth", "details": {}},
        )
        self.assertEqual(create_profile.status_code, 401)

        list_profiles = self.client.get("/api/profiles")
        self.assertEqual(list_profiles.status_code, 401)


if __name__ == "__main__":
    unittest.main()
