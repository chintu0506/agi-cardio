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

    def _signup_verify_login(self, name, email, mobile, password, role, login_value=None):
        initiate = self.client.post(
            "/api/auth/signup/initiate",
            json={"name": name, "email": email, "mobile": mobile, "password": password, "role": role},
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
            json={"login": login_value or email or mobile, "password": password},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        login_payload = login.get_json()
        self.assertTrue(login_payload.get("token"))
        return login_payload

    def _resolve_otp_code(self, otp_id, payload):
        otp_code = payload.get("otp_preview")
        if otp_code:
            return otp_code
        conn = storage.get_db()
        try:
            row = conn.execute(
                "SELECT otp_code FROM otp_codes WHERE otp_id = ?",
                (otp_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            return row["otp_code"]
        finally:
            conn.close()

    def test_patient_profile_diagnosis_history_workflow(self):
        login_payload = self._signup_verify_login(
            name="E2E Patient",
            email="patient.e2e@example.com",
            mobile="",
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

    def test_mobile_signup_and_mobile_login_workflow(self):
        mobile = "917777666655"
        login_payload = self._signup_verify_login(
            name="Mobile Patient",
            email="",
            mobile=mobile,
            password="pass1234",
            role="patient",
            login_value=mobile,
        )
        token = login_payload["token"]
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        user = me.get_json()["user"]
        self.assertEqual(user["role"], "patient")
        self.assertTrue(str(user.get("mobile") or "").endswith("7777666655"))

    def test_contact_update_via_otp_for_email_and_mobile(self):
        login_payload = self._signup_verify_login(
            name="Contact Update Patient",
            email="contact.old@example.com",
            mobile="919999000111",
            password="pass1234",
            role="patient",
        )
        token = login_payload["token"]
        headers = {"Authorization": f"Bearer {token}"}

        new_email = "contact.new@example.com"
        init_email = self.client.post(
            "/api/auth/contact-update/initiate",
            headers={**headers, "Content-Type": "application/json"},
            json={"type": "email", "value": new_email},
        )
        self.assertEqual(init_email.status_code, 200, init_email.get_data(as_text=True))
        init_email_payload = init_email.get_json()
        email_otp_id = init_email_payload.get("otp_id")
        self.assertTrue(email_otp_id)
        email_otp = self._resolve_otp_code(email_otp_id, init_email_payload)

        verify_email = self.client.post(
            "/api/auth/contact-update/verify",
            headers={**headers, "Content-Type": "application/json"},
            json={"otp_id": email_otp_id, "otp_code": email_otp},
        )
        self.assertEqual(verify_email.status_code, 200, verify_email.get_data(as_text=True))
        self.assertEqual(verify_email.get_json()["user"]["email"], new_email)

        me_after_email = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_after_email.status_code, 200)
        self.assertEqual(me_after_email.get_json()["user"]["email"], new_email)

        login_new_email = self.client.post(
            "/api/auth/login",
            json={"login": new_email, "password": "pass1234"},
        )
        self.assertEqual(login_new_email.status_code, 200, login_new_email.get_data(as_text=True))

        new_mobile = "919888777666"
        init_mobile = self.client.post(
            "/api/auth/contact-update/initiate",
            headers={**headers, "Content-Type": "application/json"},
            json={"type": "mobile", "value": new_mobile},
        )
        self.assertEqual(init_mobile.status_code, 200, init_mobile.get_data(as_text=True))
        init_mobile_payload = init_mobile.get_json()
        mobile_otp_id = init_mobile_payload.get("otp_id")
        self.assertTrue(mobile_otp_id)
        mobile_otp = self._resolve_otp_code(mobile_otp_id, init_mobile_payload)

        verify_mobile = self.client.post(
            "/api/auth/contact-update/verify",
            headers={**headers, "Content-Type": "application/json"},
            json={"otp_id": mobile_otp_id, "otp_code": mobile_otp},
        )
        self.assertEqual(verify_mobile.status_code, 200, verify_mobile.get_data(as_text=True))
        self.assertEqual(verify_mobile.get_json()["user"]["mobile"], new_mobile)

        me_after_mobile = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me_after_mobile.status_code, 200)
        self.assertEqual(me_after_mobile.get_json()["user"]["mobile"], new_mobile)

        login_new_mobile = self.client.post(
            "/api/auth/login",
            json={"login": new_mobile, "password": "pass1234"},
        )
        self.assertEqual(login_new_mobile.status_code, 200, login_new_mobile.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
