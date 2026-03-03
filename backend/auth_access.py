import os
import json
import random
import re
import smtplib
import uuid
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps
from urllib import error as urlerror, parse, request as urlrequest

from flask import request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

SESSIONS = {}


def _make_user_id(role):
    prefix = "DOC" if role == "doctor" else "PAT"
    return f"{prefix}-{random.randint(10000, 99999)}"


def _generate_unique_user_id(conn, role):
    for _ in range(30):
        candidate = _make_user_id(role)
        hit = conn.execute("SELECT id FROM users WHERE user_id = ?", (candidate,)).fetchone()
        if not hit:
            return candidate
    raise RuntimeError("Could not generate unique user ID")


def _generate_otp_code():
    return f"{random.randint(100000, 999999)}"


def _clean_optional_contact(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.lower() in {"none", "null", "na", "n/a", "-"}:
        return None
    return raw


def _normalize_mobile(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _mobile_variants(value):
    digits = _normalize_mobile(value)
    variants = set()
    if digits:
        variants.add(digits)
        if len(digits) == 11 and digits.startswith("0"):
            variants.add(digits[1:])
        if len(digits) == 11 and digits.startswith("1"):
            variants.add(digits[1:])
        if len(digits) == 12 and digits.startswith("91"):
            variants.add(digits[2:])
    return variants


def _user_exists_by_contact(conn, *, email=None, mobile=None):
    if email:
        hit = conn.execute("SELECT id FROM users WHERE lower(ifnull(email,'')) = ?", (email.lower(),)).fetchone()
        if hit:
            return True
    mobile_keys = _mobile_variants(mobile)
    if not mobile_keys:
        return False
    rows = conn.execute("SELECT mobile FROM users WHERE mobile IS NOT NULL").fetchall()
    for row in rows:
        stored_mobile = row["mobile"]
        if not stored_mobile:
            continue
        stored_keys = _mobile_variants(stored_mobile)
        if stored_keys.intersection(mobile_keys):
            return True
    return False


def _contact_used_by_other_user(conn, *, email=None, mobile=None, exclude_user_id=None):
    if email:
        if exclude_user_id:
            hit = conn.execute(
                "SELECT 1 FROM users WHERE lower(ifnull(email,'')) = ? AND user_id != ?",
                (email.lower(), exclude_user_id),
            ).fetchone()
        else:
            hit = conn.execute(
                "SELECT 1 FROM users WHERE lower(ifnull(email,'')) = ?",
                (email.lower(),),
            ).fetchone()
        if hit:
            return True
    mobile_keys = _mobile_variants(mobile)
    if not mobile_keys:
        return False
    if exclude_user_id:
        rows = conn.execute(
            "SELECT user_id, mobile FROM users WHERE mobile IS NOT NULL AND user_id != ?",
            (exclude_user_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT user_id, mobile FROM users WHERE mobile IS NOT NULL").fetchall()
    for row in rows:
        stored_mobile = row["mobile"]
        if not stored_mobile:
            continue
        stored_keys = _mobile_variants(stored_mobile)
        if stored_keys.intersection(mobile_keys):
            return True
    return False


def _find_user_for_login(conn, login_value):
    login = str(login_value or "").strip()
    if not login:
        return None
    login_email = login.lower()
    row = conn.execute(
        """SELECT user_id, name, email, mobile, password_hash, role, created_at
           FROM users WHERE lower(ifnull(email,'')) = ?""",
        (login_email,),
    ).fetchone()
    if row:
        return row

    login_mobile_keys = _mobile_variants(login)
    if not login_mobile_keys:
        return None
    rows = conn.execute(
        """SELECT user_id, name, email, mobile, password_hash, role, created_at
           FROM users WHERE mobile IS NOT NULL"""
    ).fetchall()
    for candidate in rows:
        if _mobile_variants(candidate["mobile"]).intersection(login_mobile_keys):
            return candidate
    return None


def _looks_like_email(value):
    raw = str(value or "").strip()
    if not raw:
        return False
    if "@" in raw:
        return True
    return any(ch.isalpha() for ch in raw)


def _truthy_env(name, default=False):
    val = os.getenv(name)
    if val is None:
        return bool(default)
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _smtp_config():
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASS", "").strip(),
        "sender": os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USER", "").strip(),
        "use_tls": _truthy_env("SMTP_USE_TLS", True),
    }


def _twilio_config():
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not (sid and token and from_number):
        return None
    return {"sid": sid, "token": token, "from_number": from_number}


def _to_e164_mobile(value):
    digits = _normalize_mobile(value)
    if not digits:
        return None
    if str(value).strip().startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        default_cc = os.getenv("OTP_DEFAULT_COUNTRY_CODE", "+91").strip()
        cc_digits = _normalize_mobile(default_cc) or "91"
        return f"+{cc_digits}{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        default_cc = os.getenv("OTP_DEFAULT_COUNTRY_CODE", "+91").strip()
        cc_digits = _normalize_mobile(default_cc) or "91"
        return f"+{cc_digits}{digits[1:]}"
    if len(digits) >= 11:
        return f"+{digits}"
    return f"+{digits}"


def _send_email_otp(email, otp_code):
    cfg = _smtp_config()
    if not cfg:
        return False, "Email delivery not configured (SMTP_* env vars missing)."
    if not cfg["sender"]:
        return False, "Email sender missing (set SMTP_FROM or SMTP_USER)."
    msg = EmailMessage()
    msg["Subject"] = "AGI CardioSense OTP"
    msg["From"] = cfg["sender"]
    msg["To"] = email
    msg.set_content(
        f"Your AGI CardioSense OTP is {otp_code}. It expires in 5 minutes. Do not share this code."
    )
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
            if cfg["use_tls"]:
                smtp.starttls()
            if cfg["user"] and cfg["password"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
        return True, "OTP sent via email."
    except Exception as e:
        return False, f"Email send failed: {e}"


def _send_sms_otp(mobile, otp_code):
    cfg = _twilio_config()
    if not cfg:
        return False, "SMS delivery not configured (TWILIO_* env vars missing)."
    to_number = _to_e164_mobile(mobile)
    if not to_number:
        return False, "Invalid mobile number."
    body = f"Your AGI CardioSense OTP is {otp_code}. Valid for 5 minutes."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
    data = parse.urlencode(
        {
            "From": cfg["from_number"],
            "To": to_number,
            "Body": body,
        }
    ).encode("utf-8")
    req = urlrequest.Request(url, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    auth_token = f"{cfg['sid']}:{cfg['token']}".encode("utf-8")
    import base64
    req.add_header("Authorization", f"Basic {base64.b64encode(auth_token).decode('ascii')}")
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if int(getattr(resp, "status", 200)) >= 400:
                return False, f"SMS send failed (HTTP {getattr(resp, 'status', 'unknown')}): {body[:220]}"
            return True, "OTP sent via SMS."
    except urlerror.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return False, f"SMS send failed (HTTP {e.code}): {body[:260] or str(e)}"
    except Exception as e:
        return False, f"SMS send failed: {e}"


def _deliver_otp(*, email=None, mobile=None, otp_code=None):
    if email:
        ok, note = _send_email_otp(email, otp_code)
        if ok:
            return {"delivered": True, "delivery": "email", "note": note}
        return {"delivered": False, "delivery": "email", "note": note}
    if mobile:
        ok, note = _send_sms_otp(mobile, otp_code)
        if ok:
            return {"delivered": True, "delivery": "sms", "note": note}
        return {"delivered": False, "delivery": "sms", "note": note}
    return {"delivered": False, "delivery": "unknown", "note": "No delivery target."}


def _cleanup_old_otps(conn):
    conn.execute("DELETE FROM otp_codes WHERE expires_at < ?", (datetime.now().isoformat(),))
    conn.commit()


def _create_otp_record(
    conn,
    *,
    user_contact,
    purpose,
    ttl_minutes=5,
    attempts_left=5,
    user_id=None,
    name=None,
    email=None,
    mobile=None,
    role=None,
    password_hash=None,
):
    _cleanup_old_otps(conn)
    otp_id = uuid.uuid4().hex
    otp_code = _generate_otp_code()
    now = datetime.now()
    expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()
    conn.execute(
        """INSERT INTO otp_codes
           (otp_id, user_contact, otp_code, purpose, user_id, name, email, mobile, role, password_hash,
            attempts_left, verified, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (
            otp_id,
            user_contact,
            otp_code,
            purpose,
            user_id,
            name,
            email,
            mobile,
            role,
            password_hash,
            int(attempts_left),
            expires_at,
            now.isoformat(),
        ),
    )
    conn.commit()
    return {"otp_id": otp_id, "otp_code": otp_code, "expires_at": expires_at}


def _verify_otp_record(conn, *, otp_id, otp_code, purpose):
    row = conn.execute(
        "SELECT * FROM otp_codes WHERE otp_id = ? AND purpose = ? AND verified = 0",
        (otp_id, purpose),
    ).fetchone()
    if not row:
        return None, "OTP session not found."
    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        conn.execute("DELETE FROM otp_codes WHERE id = ?", (row["id"],))
        conn.commit()
        return None, "OTP expired. Please request a new OTP."
    if str(row["otp_code"]) != str(otp_code):
        left = max(0, int(row["attempts_left"]) - 1)
        conn.execute("UPDATE otp_codes SET attempts_left = ? WHERE id = ?", (left, row["id"]))
        conn.commit()
        if left <= 0:
            conn.execute("DELETE FROM otp_codes WHERE id = ?", (row["id"],))
            conn.commit()
            return None, "OTP attempts exceeded. Request a new OTP."
        return None, f"Invalid OTP. Attempts left: {left}."
    conn.execute("UPDATE otp_codes SET verified = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    return row, None


def _token_from_request():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _current_user():
    token = _token_from_request()
    if not token:
        return None
    sess = SESSIONS.get(token)
    if not sess:
        return None
    if datetime.fromisoformat(sess["expires_at"]) < datetime.now():
        SESSIONS.pop(token, None)
        return None
    return sess["user"]


def install_auth_access_routes(app, get_db, cors, upload_dir):
    allowed_record_types = {"ecg", "mri", "cathlab", "report", "lab", "imaging", "other"}

    def file_url_and_type(patient_user_id, file_path):
        parts = os.path.normpath(file_path).split(os.sep)
        tail = os.path.basename(file_path)
        if len(parts) >= 3 and parts[-3] == patient_user_id:
            record_type = parts[-2]
            return f"/uploads/{patient_user_id}/{record_type}/{tail}", record_type
        return f"/uploads/{patient_user_id}/{tail}", "other"
    def auth_required(role=None):
        def deco(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                user = _current_user()
                if not user:
                    return cors({"error": "Unauthorized"}, 401)
                if role and user.get("role") != role:
                    return cors({"error": "Forbidden for this role"}, 403)
                request.current_user = user
                return fn(*args, **kwargs)

            return wrapped

        return deco

    def _create_login_session(user_row):
        token = uuid.uuid4().hex
        expires_at = (datetime.now() + timedelta(hours=12)).isoformat()
        user = {
            "user_id": user_row["user_id"],
            "name": user_row["name"],
            "email": user_row["email"],
            "mobile": user_row["mobile"],
            "role": user_row["role"],
            "created_at": user_row["created_at"],
        }
        SESSIONS[token] = {"user": user, "expires_at": expires_at}
        return token, expires_at, user

    @app.route("/api/auth/signup/initiate", methods=["GET", "POST"])
    def auth_signup_initiate():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        name = str(body.get("name", "")).strip()
        contact = _clean_optional_contact(body.get("contact"))
        email = _clean_optional_contact(body.get("email"))
        mobile = _clean_optional_contact(body.get("mobile"))
        if contact and not email and _looks_like_email(contact):
            email = contact
        if contact and not mobile and not _looks_like_email(contact):
            mobile = contact
        if email:
            email = email.lower()
        mobile = _normalize_mobile(mobile)
        if not mobile:
            mobile = None
        password = str(body.get("password", ""))
        role = str(body.get("role", "")).strip().lower()

        if role not in ["doctor", "patient"]:
            return cors({"error": "Role must be 'doctor' or 'patient'."}, 400)
        if not name:
            return cors({"error": "Name is required."}, 400)
        if not email and not mobile:
            return cors({"error": "Provide email or mobile for signup OTP."}, 400)
        if email and not _looks_like_email(email):
            return cors({"error": "Provide a valid email address for signup OTP."}, 400)
        if mobile and len(mobile) < 10:
            return cors({"error": "Provide a valid mobile number (at least 10 digits)."}, 400)
        if len(password) < 6:
            return cors({"error": "Password must be at least 6 characters."}, 400)

        conn = get_db()
        try:
            if _user_exists_by_contact(conn, email=email, mobile=mobile):
                return cors({"error": "Email or mobile already registered."}, 409)
            target = email or mobile
            use_email = bool(email)
            otp = _create_otp_record(
                conn,
                user_contact=target,
                purpose="signup",
                ttl_minutes=5,
                attempts_left=5,
                name=name,
                email=email,
                mobile=mobile,
                role=role,
                password_hash=generate_password_hash(password),
            )
            delivery_info = _deliver_otp(
                email=email if use_email else None,
                mobile=mobile if not use_email else None,
                otp_code=otp["otp_code"],
            )
            allow_preview = _truthy_env("OTP_ALLOW_PREVIEW", True)
            response = {
                "message": f"OTP sent to {target}. Verify to complete signup.",
                "otp_id": otp["otp_id"],
                "expires_at": otp["expires_at"],
                "delivery": delivery_info["delivery"],
                "delivery_target": target,
                "delivery_status": "sent" if delivery_info["delivered"] else "failed",
                "delivery_note": delivery_info["note"],
            }
            if allow_preview:
                response["otp_preview"] = otp["otp_code"]
                response["otp_note"] = (
                    "OTP preview enabled for testing."
                    if delivery_info["delivered"]
                    else "Provider delivery failed/unavailable. Use OTP preview for testing."
                )
            return cors(
                response
            )
        finally:
            conn.close()

    @app.route("/api/auth/signup/verify", methods=["GET", "POST"])
    def auth_signup_verify():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        otp_id = str(body.get("otp_id", "")).strip()
        otp_code = str(body.get("otp_code", "")).strip()
        if not otp_id or not otp_code:
            return cors({"error": "otp_id and otp_code are required."}, 400)

        conn = get_db()
        try:
            row, err = _verify_otp_record(conn, otp_id=otp_id, otp_code=otp_code, purpose="signup")
            if err:
                return cors({"error": err}, 400)
            email = _clean_optional_contact(row["email"])
            if email:
                email = email.lower()
            mobile = _normalize_mobile(_clean_optional_contact(row["mobile"]))
            if not mobile:
                mobile = None
            if _user_exists_by_contact(conn, email=email, mobile=mobile):
                return cors({"error": "Email or mobile already registered."}, 409)

            user_id = _generate_unique_user_id(conn, row["role"])
            created_at = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO users (user_id, name, email, mobile, password_hash, role, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, row["name"], email, mobile, row["password_hash"], row["role"], created_at),
            )
            conn.execute("DELETE FROM otp_codes WHERE otp_id = ?", (otp_id,))
            conn.commit()
            return cors(
                {
                    "message": "Signup completed after OTP verification.",
                    "user": {
                        "user_id": user_id,
                        "name": row["name"],
                        "email": email,
                        "mobile": mobile,
                        "role": row["role"],
                        "created_at": created_at,
                    },
                },
                201,
            )
        finally:
            conn.close()

    @app.route("/api/auth/login", methods=["POST"])
    def auth_login():
        body = request.get_json(silent=True) or {}
        login = str(body.get("login", "")).strip()
        password = str(body.get("password", ""))
        if not login or not password:
            return cors({"error": "Login and password are required."}, 400)

        conn = get_db()
        try:
            row = _find_user_for_login(conn, login)
            if not row or not check_password_hash(row["password_hash"], password):
                return cors({"error": "Invalid credentials."}, 401)
            token, expires_at, user = _create_login_session(row)
            return cors(
                {
                    "message": "Login successful.",
                    "token": token,
                    "expires_at": expires_at,
                    "user": user,
                }
            )
        finally:
            conn.close()

    @app.route("/api/auth/forgot-password/initiate", methods=["GET", "POST"])
    def auth_forgot_password_initiate():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        mobile = _normalize_mobile(_clean_optional_contact(body.get("mobile")))
        if not mobile or len(mobile) < 10:
            return cors({"error": "Provide a valid mobile number (at least 10 digits)."}, 400)

        conn = get_db()
        try:
            row = _find_user_for_login(conn, mobile)
            if not row:
                return cors({"error": "No account found for this mobile number."}, 404)
            row_mobile = _normalize_mobile(row["mobile"])
            if not row_mobile:
                return cors({"error": "Selected account has no mobile number configured."}, 400)
            if not _mobile_variants(row_mobile).intersection(_mobile_variants(mobile)):
                return cors({"error": "No account found for this mobile number."}, 404)

            otp = _create_otp_record(
                conn,
                user_contact=row_mobile,
                purpose="forgot_password_login",
                ttl_minutes=5,
                attempts_left=5,
                user_id=row["user_id"],
                mobile=row_mobile,
            )
            delivery_info = _deliver_otp(mobile=row_mobile, otp_code=otp["otp_code"])
            allow_preview = _truthy_env("OTP_ALLOW_PREVIEW", True)
            response = {
                "message": f"OTP sent to {row_mobile}. Verify OTP to login.",
                "otp_id": otp["otp_id"],
                "expires_at": otp["expires_at"],
                "delivery": delivery_info["delivery"],
                "delivery_target": row_mobile,
                "delivery_status": "sent" if delivery_info["delivered"] else "failed",
                "delivery_note": delivery_info["note"],
            }
            if allow_preview:
                response["otp_preview"] = otp["otp_code"]
                response["otp_note"] = (
                    "OTP preview enabled for testing."
                    if delivery_info["delivered"]
                    else "Provider delivery failed/unavailable. Use OTP preview for testing."
                )
            return cors(response)
        finally:
            conn.close()

    @app.route("/api/auth/forgot-password/verify", methods=["GET", "POST"])
    def auth_forgot_password_verify():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        otp_id = str(body.get("otp_id", "")).strip()
        otp_code = str(body.get("otp_code", "")).strip()
        new_password = str(body.get("new_password", ""))
        if not otp_id or not otp_code:
            return cors({"error": "otp_id and otp_code are required."}, 400)
        if len(new_password) < 6:
            return cors({"error": "new_password must be at least 6 characters."}, 400)

        conn = get_db()
        try:
            row, err = _verify_otp_record(
                conn,
                otp_id=otp_id,
                otp_code=otp_code,
                purpose="forgot_password_login",
            )
            if err:
                return cors({"error": err}, 400)
            user_id = str(row["user_id"] or "").strip()
            if not user_id:
                return cors({"error": "OTP session has no user attached."}, 400)
            user_row = conn.execute(
                """SELECT user_id, name, email, mobile, password_hash, role, created_at
                   FROM users WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
            if not user_row:
                return cors({"error": "User not found."}, 404)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE user_id = ?",
                (generate_password_hash(new_password), user_id),
            )
            conn.execute("DELETE FROM otp_codes WHERE otp_id = ?", (otp_id,))
            conn.commit()

            # Invalidate old sessions after password reset.
            for token, sess in list(SESSIONS.items()):
                sess_user = sess.get("user", {})
                if str(sess_user.get("user_id") or "") == user_id:
                    SESSIONS.pop(token, None)

            user_row = conn.execute(
                """SELECT user_id, name, email, mobile, password_hash, role, created_at
                   FROM users WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
            token, expires_at, user = _create_login_session(user_row)
            return cors(
                {
                    "message": "OTP verified. Password updated and login successful.",
                    "token": token,
                    "expires_at": expires_at,
                    "user": user,
                }
            )
        finally:
            conn.close()

    @app.route("/api/auth/login/initiate", methods=["GET", "POST"])
    def auth_login_initiate_compat():
        return cors({"error": "Login OTP is disabled. Use /api/auth/login with password."}, 400)

    @app.route("/api/auth/login/verify", methods=["GET", "POST"])
    def auth_login_verify():
        return cors({"error": "Login OTP is disabled. Use /api/auth/login with password."}, 400)

    @app.route("/api/auth/signup", methods=["POST"])
    def auth_signup_compat():
        return cors({"error": "OTP required. Use /api/auth/signup/initiate then /api/auth/signup/verify."}, 400)

    @app.route("/api/auth/me", methods=["GET"])
    @auth_required()
    def auth_me():
        conn = get_db()
        try:
            row = conn.execute(
                """SELECT user_id, name, email, mobile, role, created_at
                   FROM users WHERE user_id = ?""",
                (request.current_user["user_id"],),
            ).fetchone()
            if not row:
                return cors({"error": "User not found."}, 404)
            user = dict(row)
            token = _token_from_request()
            if token and token in SESSIONS:
                SESSIONS[token]["user"] = user
            return cors({"user": user})
        finally:
            conn.close()

    @app.route("/api/auth/contact-update/initiate", methods=["GET", "POST"])
    @auth_required()
    def auth_contact_update_initiate():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        contact_type = str(body.get("type", "")).strip().lower()
        value_raw = _clean_optional_contact(body.get("value"))
        if contact_type not in {"email", "mobile"}:
            return cors({"error": "type must be 'email' or 'mobile'."}, 400)
        if not value_raw:
            return cors({"error": "value is required."}, 400)

        conn = get_db()
        try:
            user_id = request.current_user["user_id"]
            row = conn.execute(
                "SELECT user_id, email, mobile FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return cors({"error": "User not found."}, 404)

            target_email = None
            target_mobile = None
            if contact_type == "email":
                target_email = str(value_raw).strip().lower()
                if not _looks_like_email(target_email):
                    return cors({"error": "Provide a valid email address."}, 400)
                current_email = str(row["email"] or "").strip().lower()
                if target_email == current_email:
                    return cors({"error": "Email is already your current email."}, 400)
                if _contact_used_by_other_user(conn, email=target_email, exclude_user_id=user_id):
                    return cors({"error": "Email is already in use."}, 409)
            else:
                target_mobile = _normalize_mobile(value_raw)
                if len(target_mobile) < 10:
                    return cors({"error": "Provide a valid mobile number (at least 10 digits)."}, 400)
                current_mobile = _normalize_mobile(row["mobile"] or "")
                if target_mobile == current_mobile:
                    return cors({"error": "Mobile is already your current mobile number."}, 400)
                if _contact_used_by_other_user(conn, mobile=target_mobile, exclude_user_id=user_id):
                    return cors({"error": "Mobile number is already in use."}, 409)

            target = target_email or target_mobile
            otp = _create_otp_record(
                conn,
                user_contact=target,
                purpose="contact_update",
                ttl_minutes=5,
                attempts_left=5,
                user_id=user_id,
                email=target_email,
                mobile=target_mobile,
            )
            delivery_info = _deliver_otp(
                email=target_email,
                mobile=target_mobile,
                otp_code=otp["otp_code"],
            )
            allow_preview = _truthy_env("OTP_ALLOW_PREVIEW", True)
            response = {
                "message": f"OTP sent to {target}. Verify to apply contact update.",
                "otp_id": otp["otp_id"],
                "expires_at": otp["expires_at"],
                "type": contact_type,
                "delivery": delivery_info["delivery"],
                "delivery_target": target,
                "delivery_status": "sent" if delivery_info["delivered"] else "failed",
                "delivery_note": delivery_info["note"],
            }
            if allow_preview:
                response["otp_preview"] = otp["otp_code"]
                response["otp_note"] = (
                    "OTP preview enabled for testing."
                    if delivery_info["delivered"]
                    else "Provider delivery failed/unavailable. Use OTP preview for testing."
                )
            return cors(response)
        finally:
            conn.close()

    @app.route("/api/auth/contact-update/verify", methods=["GET", "POST"])
    @auth_required()
    def auth_contact_update_verify():
        body = request.get_json(silent=True) or {}
        if request.method == "GET":
            body = request.args.to_dict() or body
        otp_id = str(body.get("otp_id", "")).strip()
        otp_code = str(body.get("otp_code", "")).strip()
        if not otp_id or not otp_code:
            return cors({"error": "otp_id and otp_code are required."}, 400)

        conn = get_db()
        try:
            row, err = _verify_otp_record(conn, otp_id=otp_id, otp_code=otp_code, purpose="contact_update")
            if err:
                return cors({"error": err}, 400)
            user_id = request.current_user["user_id"]
            otp_user_id = str(row["user_id"] or "").strip()
            if otp_user_id != user_id:
                return cors({"error": "OTP session does not belong to current user."}, 403)

            target_email = _clean_optional_contact(row["email"])
            if target_email:
                target_email = target_email.lower()
            target_mobile = _normalize_mobile(_clean_optional_contact(row["mobile"]))
            if not target_mobile:
                target_mobile = None
            if not target_email and not target_mobile:
                return cors({"error": "OTP session has no pending contact update."}, 400)

            if target_email and _contact_used_by_other_user(conn, email=target_email, exclude_user_id=user_id):
                return cors({"error": "Email is already in use."}, 409)
            if target_mobile and _contact_used_by_other_user(conn, mobile=target_mobile, exclude_user_id=user_id):
                return cors({"error": "Mobile number is already in use."}, 409)

            if target_email:
                conn.execute("UPDATE users SET email = ? WHERE user_id = ?", (target_email, user_id))
            if target_mobile:
                conn.execute("UPDATE users SET mobile = ? WHERE user_id = ?", (target_mobile, user_id))
            conn.execute("DELETE FROM otp_codes WHERE otp_id = ?", (otp_id,))

            refreshed = conn.execute(
                """SELECT user_id, name, email, mobile, role, created_at
                   FROM users WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
            if not refreshed:
                conn.rollback()
                return cors({"error": "User not found after contact update."}, 404)
            conn.commit()

            refreshed_user = dict(refreshed)
            for token, sess in list(SESSIONS.items()):
                sess_user = sess.get("user", {})
                if str(sess_user.get("user_id")) == user_id:
                    sess["user"] = refreshed_user.copy()
                    SESSIONS[token] = sess

            return cors({"message": "Contact updated successfully.", "user": refreshed_user})
        finally:
            conn.close()

    @app.route("/api/doctors", methods=["GET"])
    @auth_required()
    def list_doctors():
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT user_id, name, email, mobile, created_at
                   FROM users
                   WHERE role = 'doctor'
                   ORDER BY name ASC, user_id ASC"""
            ).fetchall()
        finally:
            conn.close()
        return cors([dict(r) for r in rows])

    @app.route("/api/patient/appointments", methods=["GET", "POST"])
    @auth_required("patient")
    def patient_appointments():
        patient_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            if request.method == "POST":
                body = request.get_json(force=True) or {}
                doctor_user_id = str(body.get("doctor_user_id", "")).strip()
                scheduled_at = str(body.get("scheduled_at", "")).strip() or datetime.now().isoformat()
                notes = str(body.get("notes", "")).strip()
                consult_link = str(body.get("consult_link", "")).strip()
                if not doctor_user_id:
                    return cors({"error": "doctor_user_id is required."}, 400)
                d = conn.execute(
                    "SELECT user_id FROM users WHERE user_id = ? AND role = 'doctor'",
                    (doctor_user_id,),
                ).fetchone()
                if not d:
                    return cors({"error": "Doctor not found."}, 404)

                status = "pending"
                created_at = datetime.now().isoformat()
                cur = conn.execute(
                    """INSERT INTO doctor_appointments
                       (doctor_user_id, patient_user_id, scheduled_at, status, consult_link, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doctor_user_id, patient_user_id, scheduled_at, status, consult_link, notes, created_at),
                )
                conn.commit()
                return cors(
                    {
                        "id": cur.lastrowid,
                        "doctor_user_id": doctor_user_id,
                        "patient_user_id": patient_user_id,
                        "scheduled_at": scheduled_at,
                        "status": status,
                        "consult_link": consult_link,
                        "notes": notes,
                        "created_at": created_at,
                    },
                    201,
                )

            rows = conn.execute(
                """SELECT a.id, a.doctor_user_id, d.name AS doctor_name, d.mobile AS doctor_mobile,
                          a.scheduled_at, a.status, a.consult_link, a.notes, a.created_at
                   FROM doctor_appointments a
                   LEFT JOIN users d ON d.user_id = a.doctor_user_id
                   WHERE a.patient_user_id = ?
                   ORDER BY a.scheduled_at ASC, a.id ASC""",
                (patient_user_id,),
            ).fetchall()
            return cors([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route("/api/patient-records", methods=["GET"])
    @auth_required("patient")
    def patient_records():
        patient_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT id, file_name, file_path, file_type, diagnosis_summary, upload_date
                   FROM patient_records WHERE patient_user_id = ? ORDER BY id DESC""",
                (patient_user_id,),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            file_url, record_type = file_url_and_type(patient_user_id, r["file_path"])
            out.append(
                {
                    "id": r["id"],
                    "file_name": r["file_name"],
                    "file_type": r["file_type"],
                    "record_type": record_type,
                    "diagnosis_summary": r["diagnosis_summary"],
                    "upload_date": r["upload_date"],
                    "file_url": file_url,
                }
            )
        return cors(out)

    @app.route("/api/patient-records/upload", methods=["POST"])
    @auth_required("patient")
    def upload_patient_record():
        if "file" not in request.files:
            return cors({"error": "Missing file field 'file'."}, 400)
        f = request.files["file"]
        if not f or not f.filename:
            return cors({"error": "No file selected."}, 400)

        summary = str(request.form.get("diagnosis_summary", "")).strip()
        doctor_user_id = str(request.form.get("doctor_user_id", "")).strip()
        record_type = str(request.form.get("record_type", "other")).strip().lower()
        if record_type not in allowed_record_types:
            record_type = "other"
        patient_user_id = request.current_user["user_id"]
        safe_name = os.path.basename(f.filename).replace("\x00", "")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
        if not safe_name:
            safe_name = "upload.bin"

        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_name = f"{stamp}_{safe_name}"
        user_dir = os.path.join(upload_dir, patient_user_id, record_type)
        os.makedirs(user_dir, exist_ok=True)
        abs_path = os.path.join(user_dir, saved_name)
        f.save(abs_path)
        rel_path = os.path.relpath(abs_path, os.path.dirname(upload_dir))
        upload_date = datetime.now().isoformat()

        conn = get_db()
        try:
            if doctor_user_id:
                d = conn.execute(
                    "SELECT user_id FROM users WHERE user_id = ? AND role = 'doctor'",
                    (doctor_user_id,),
                ).fetchone()
                if not d:
                    return cors({"error": "Doctor not found for this upload queue."}, 404)
            cur = conn.execute(
                """INSERT INTO patient_records
                   (patient_user_id, uploaded_by_user_id, file_name, file_path, file_type, diagnosis_summary, upload_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (patient_user_id, patient_user_id, safe_name, rel_path, f.mimetype or "", summary, upload_date),
            )
            if doctor_user_id:
                queued = conn.execute(
                    """SELECT id FROM doctor_appointments
                       WHERE doctor_user_id = ? AND patient_user_id = ?
                         AND lower(ifnull(status,'')) IN ('pending', 'accepted')
                       ORDER BY id ASC LIMIT 1""",
                    (doctor_user_id, patient_user_id),
                ).fetchone()
                if not queued:
                    conn.execute(
                        """INSERT INTO doctor_appointments
                           (doctor_user_id, patient_user_id, scheduled_at, status, consult_link, notes, created_at)
                           VALUES (?, ?, ?, 'pending', '', ?, ?)""",
                        (
                            doctor_user_id,
                            patient_user_id,
                            upload_date,
                            "Auto-queued from patient upload",
                            upload_date,
                        ),
                    )
            conn.commit()
            rec_id = cur.lastrowid
        finally:
            conn.close()

        return cors(
            {
                "id": rec_id,
                "patient_user_id": patient_user_id,
                "file_name": safe_name,
                "record_type": record_type,
                "file_url": f"/uploads/{patient_user_id}/{record_type}/{saved_name}",
                "diagnosis_summary": summary,
                "doctor_user_id": doctor_user_id or None,
                "upload_date": upload_date,
            },
            201,
        )

    @app.route("/api/doctor/patient/<patient_user_id>/records/upload", methods=["POST"])
    @auth_required("doctor")
    def doctor_upload_patient_record(patient_user_id):
        if "file" not in request.files:
            return cors({"error": "Missing file field 'file'."}, 400)
        f = request.files["file"]
        if not f or not f.filename:
            return cors({"error": "No file selected."}, 400)

        conn = get_db()
        try:
            patient = conn.execute(
                "SELECT id FROM users WHERE user_id = ? AND role = 'patient'",
                (patient_user_id,),
            ).fetchone()
            if not patient:
                return cors({"error": "Patient not found."}, 404)
        finally:
            conn.close()

        summary = str(request.form.get("diagnosis_summary", "")).strip()
        record_type = str(request.form.get("record_type", "other")).strip().lower()
        if record_type not in allowed_record_types:
            record_type = "other"
        safe_name = os.path.basename(f.filename).replace("\x00", "")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
        if not safe_name:
            safe_name = "upload.bin"

        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        saved_name = f"{stamp}_{safe_name}"
        user_dir = os.path.join(upload_dir, patient_user_id, record_type)
        os.makedirs(user_dir, exist_ok=True)
        abs_path = os.path.join(user_dir, saved_name)
        f.save(abs_path)
        rel_path = os.path.relpath(abs_path, os.path.dirname(upload_dir))
        upload_date = datetime.now().isoformat()

        conn = get_db()
        try:
            cur = conn.execute(
                """INSERT INTO patient_records
                   (patient_user_id, uploaded_by_user_id, file_name, file_path, file_type, diagnosis_summary, upload_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (patient_user_id, request.current_user["user_id"], safe_name, rel_path, f.mimetype or "", summary, upload_date),
            )
            conn.commit()
            rec_id = cur.lastrowid
        finally:
            conn.close()

        return cors(
            {
                "id": rec_id,
                "patient_user_id": patient_user_id,
                "uploaded_by_user_id": request.current_user["user_id"],
                "file_name": safe_name,
                "record_type": record_type,
                "file_url": f"/uploads/{patient_user_id}/{record_type}/{saved_name}",
                "diagnosis_summary": summary,
                "upload_date": upload_date,
            },
            201,
        )

    @app.route("/uploads/<path:subpath>", methods=["GET"])
    def serve_upload(subpath):
        safe = os.path.normpath(subpath).lstrip(os.sep)
        return send_from_directory(upload_dir, safe)

    @app.route("/api/doctor/patient-records", methods=["GET"])
    @auth_required("doctor")
    def doctor_all_patient_records():
        return cors(
            {
                "error": "Global uploads feed removed. Use /api/doctor/patient/<patient_user_id> for patient-specific uploads."
            },
            410,
        )

    @app.route("/api/doctor/patient/<patient_user_id>", methods=["GET"])
    @auth_required("doctor")
    def doctor_get_patient(patient_user_id):
        conn = get_db()
        try:
            patient = conn.execute(
                """SELECT user_id, name, email, mobile, role, created_at
                   FROM users WHERE user_id = ? AND role = 'patient'""",
                (patient_user_id,),
            ).fetchone()
            if not patient:
                return cors({"error": "Patient not found."}, 404)

            records = conn.execute(
                """SELECT id, file_name, file_path, file_type, diagnosis_summary, upload_date
                   FROM patient_records WHERE patient_user_id = ? ORDER BY id DESC""",
                (patient_user_id,),
            ).fetchall()
            notes = conn.execute(
                """SELECT id, doctor_user_id, patient_user_id, prescription, remarks, ecg_signal_json, created_at
                   FROM doctor_notes WHERE patient_user_id = ? ORDER BY id DESC""",
                (patient_user_id,),
            ).fetchall()
            diagnoses = conn.execute(
                """SELECT d.id, d.report_id, d.risk_level, d.master_probability, d.result_payload, d.created_at
                   FROM diagnoses d
                   JOIN profiles p ON p.id = d.profile_id
                   WHERE p.owner_user_id = ?
                   ORDER BY d.id DESC LIMIT 30""",
                (patient_user_id,),
            ).fetchall()
            latest_profile = conn.execute(
                """SELECT id, full_name, age, sex, details_json, notes, created_at
                   FROM profiles WHERE owner_user_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (patient_user_id,),
            ).fetchone()
        finally:
            conn.close()

        rec_out = []
        for r in records:
            file_url, record_type = file_url_and_type(patient_user_id, r["file_path"])
            rec_out.append(
                {
                    "id": r["id"],
                    "file_name": r["file_name"],
                    "file_type": r["file_type"],
                    "record_type": record_type,
                    "diagnosis_summary": r["diagnosis_summary"],
                    "upload_date": r["upload_date"],
                    "file_url": file_url,
                }
            )
        notes_out = []
        for n in notes:
            item = dict(n)
            ecg = []
            try:
                raw = item.get("ecg_signal_json")
                if raw:
                    decoded = json.loads(raw)
                    if isinstance(decoded, list):
                        ecg = [float(x) for x in decoded if isinstance(x, (int, float))]
            except Exception:
                ecg = []
            item["ecg_signal"] = ecg
            item.pop("ecg_signal_json", None)
            notes_out.append(item)
        diag_out = []
        for d in diagnoses:
            item = dict(d)
            summary = ""
            try:
                payload = json.loads(item.get("result_payload") or "{}")
                top = payload.get("diseases", [])[:2]
                if top:
                    summary = ", ".join(
                        f"{x.get('name', 'Unknown')} ({float(x.get('probability', 0)):.1f}%)"
                        for x in top
                    )
            except Exception:
                summary = ""
            item["diagnosis_summary"] = summary
            item.pop("result_payload", None)
            diag_out.append(item)
        profile_out = None
        if latest_profile:
            p = dict(latest_profile)
            details = {}
            if p.get("details_json"):
                try:
                    details = json.loads(p["details_json"])
                except Exception:
                    details = {}
            profile_out = {
                "demographics": {
                    "full_name": p.get("full_name"),
                    "age": p.get("age"),
                    "sex": p.get("sex"),
                    "created_at": p.get("created_at"),
                },
                "symptoms": details.get("symptoms", []),
                "vitals": details.get("vitals", {}),
                "past_heart_conditions": details.get("existing_conditions") or details.get("past_heart_conditions"),
                "medications": details.get("medications", []),
                "notes": p.get("notes"),
                "details": details,
            }
        return cors(
            {
                "patient": dict(patient),
                "patient_profile": profile_out,
                "records": rec_out,
                "notes": notes_out,
                "diagnoses": diag_out,
            }
        )

    @app.route("/api/doctor/patient/<patient_user_id>/diagnose", methods=["POST"])
    @auth_required("doctor")
    def doctor_diagnose_patient(patient_user_id):
        body = request.get_json(force=True) or {}
        from app import generate_diagnosis  # local import to avoid circular import at module load time

        conn = get_db()
        try:
            patient = conn.execute(
                "SELECT user_id, name, role FROM users WHERE user_id = ? AND role = 'patient'",
                (patient_user_id,),
            ).fetchone()
            if not patient:
                return cors({"error": "Patient not found."}, 404)

            profile = conn.execute(
                """SELECT id FROM profiles
                   WHERE owner_user_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (patient_user_id,),
            ).fetchone()
            if not profile:
                created_at = datetime.now().isoformat()
                cur = conn.execute(
                    """INSERT INTO profiles (full_name, age, sex, owner_user_id, details_json, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (patient["name"], None, None, patient_user_id, "{}", "Auto-created by doctor diagnosis flow", created_at),
                )
                conn.commit()
                profile_id = cur.lastrowid
            else:
                profile_id = profile["id"]

            report = generate_diagnosis(body)
            created_at = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO diagnoses
                   (profile_id, report_id, risk_level, master_probability, input_payload, result_payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile_id,
                    report["report_id"],
                    report.get("risk_tier", {}).get("level", ""),
                    report.get("master_probability", 0.0),
                    json.dumps(body),
                    json.dumps(report),
                    created_at,
                ),
            )
            conn.commit()
            return cors(report, 201)
        except ValueError as e:
            return cors({"error": str(e)}, 400)
        finally:
            conn.close()

    @app.route("/api/doctor/patients", methods=["GET"])
    @auth_required("doctor")
    def doctor_list_patients():
        q = str(request.args.get("q", "")).strip().lower()
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT user_id, name, email, mobile, created_at
                   FROM users WHERE role = 'patient' ORDER BY id DESC"""
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            item = dict(r)
            if q:
                hay = " ".join(
                    [
                        str(item.get("user_id", "")).lower(),
                        str(item.get("name", "")).lower(),
                        str(item.get("mobile", "")).lower(),
                        str(item.get("email", "")).lower(),
                    ]
                )
                if q not in hay:
                    continue
            out.append(item)
        return cors(out[:200])

    @app.route("/api/doctor/dashboard", methods=["GET"])
    @auth_required("doctor")
    def doctor_dashboard():
        doctor_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            total_patients = int(
                conn.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'patient'").fetchone()["c"]
            )
            today = datetime.now().date().isoformat()
            today_appointments = int(
                conn.execute(
                    """SELECT COUNT(*) AS c FROM doctor_appointments
                       WHERE doctor_user_id = ? AND substr(scheduled_at, 1, 10) = ?""",
                    (doctor_user_id, today),
                ).fetchone()["c"]
            )
            pending_reports = int(
                conn.execute(
                    """SELECT COUNT(*) AS c FROM patient_records
                       WHERE ifnull(trim(diagnosis_summary), '') = ''"""
                ).fetchone()["c"]
            )
            uploaded_scans_to_review = pending_reports

            diag_rows = conn.execute(
                """SELECT d.risk_level, d.result_payload, d.created_at
                   FROM diagnoses d ORDER BY d.id DESC LIMIT 500"""
            ).fetchall()

            disease_map = {}
            success_hits = 0
            ai_alerts = 0
            for row in diag_rows:
                risk = str(row["risk_level"] or "").upper()
                if risk in {"HIGH", "CRITICAL"}:
                    ai_alerts += 1
                if risk in {"LOW", "MINIMAL", "MODERATE"}:
                    success_hits += 1
                try:
                    payload = json.loads(row["result_payload"] or "{}")
                    for d in payload.get("diseases", [])[:3]:
                        name = str(d.get("name") or "Unknown")
                        disease_map[name] = disease_map.get(name, 0) + 1
                except Exception:
                    pass

            diagnosis_success_rate = round((success_hits * 100.0 / max(1, len(diag_rows))), 1)

            month_rows = conn.execute(
                """SELECT substr(created_at, 1, 7) AS ym, COUNT(*) AS c
                   FROM users WHERE role = 'patient'
                   GROUP BY ym ORDER BY ym DESC LIMIT 6"""
            ).fetchall()
            monthly_patient_count = list(reversed([{"month": r["ym"], "count": int(r["c"])} for r in month_rows]))

            disease_distribution = [
                {"name": k, "count": v}
                for k, v in sorted(disease_map.items(), key=lambda kv: kv[1], reverse=True)[:8]
            ]
        finally:
            conn.close()

        return cors(
            {
                "overview": {
                    "total_patients": total_patients,
                    "today_appointments": today_appointments,
                    "pending_reports": pending_reports,
                    "uploaded_scans_to_review": uploaded_scans_to_review,
                    "ai_alerts": ai_alerts,
                },
                "charts": {
                    "disease_distribution": disease_distribution,
                    "monthly_patient_count": monthly_patient_count,
                    "diagnosis_success_rate": diagnosis_success_rate,
                },
            }
        )

    @app.route("/api/doctor/appointments", methods=["GET", "POST"])
    @auth_required("doctor")
    def doctor_appointments():
        doctor_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            if request.method == "POST":
                body = request.get_json(force=True) or {}
                patient_user_id = str(body.get("patient_user_id", "")).strip()
                scheduled_at = str(body.get("scheduled_at", "")).strip()
                status = str(body.get("status", "pending")).strip().lower() or "pending"
                consult_link = str(body.get("consult_link", "")).strip()
                notes = str(body.get("notes", "")).strip()
                if not patient_user_id or not scheduled_at:
                    return cors({"error": "patient_user_id and scheduled_at are required."}, 400)
                p = conn.execute(
                    "SELECT id FROM users WHERE user_id = ? AND role = 'patient'",
                    (patient_user_id,),
                ).fetchone()
                if not p:
                    return cors({"error": "Patient not found."}, 404)
                created_at = datetime.now().isoformat()
                cur = conn.execute(
                    """INSERT INTO doctor_appointments
                       (doctor_user_id, patient_user_id, scheduled_at, status, consult_link, notes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (doctor_user_id, patient_user_id, scheduled_at, status, consult_link, notes, created_at),
                )
                conn.commit()
                return cors(
                    {
                        "id": cur.lastrowid,
                        "doctor_user_id": doctor_user_id,
                        "patient_user_id": patient_user_id,
                        "scheduled_at": scheduled_at,
                        "status": status,
                        "consult_link": consult_link,
                        "notes": notes,
                        "created_at": created_at,
                    },
                    201,
                )

            rows = conn.execute(
                """SELECT a.id, a.patient_user_id, u.name AS patient_name, u.mobile AS patient_mobile,
                          a.scheduled_at, a.status, a.consult_link, a.notes, a.created_at
                   FROM doctor_appointments a
                   LEFT JOIN users u ON u.user_id = a.patient_user_id
                   WHERE a.doctor_user_id = ?
                   ORDER BY a.scheduled_at ASC""",
                (doctor_user_id,),
            ).fetchall()
            return cors([dict(r) for r in rows])
        finally:
            conn.close()

    @app.route("/api/doctor/appointments/<int:appointment_id>", methods=["PUT"])
    @auth_required("doctor")
    def doctor_update_appointment(appointment_id):
        body = request.get_json(force=True) or {}
        doctor_user_id = request.current_user["user_id"]
        updates = []
        params = []
        for key in ["scheduled_at", "status", "consult_link", "notes"]:
            if key in body:
                updates.append(f"{key} = ?")
                params.append(str(body.get(key, "")).strip())
        if not updates:
            return cors({"error": "No updatable fields provided."}, 400)
        params.extend([appointment_id, doctor_user_id])
        conn = get_db()
        try:
            hit = conn.execute(
                "SELECT id FROM doctor_appointments WHERE id = ? AND doctor_user_id = ?",
                (appointment_id, doctor_user_id),
            ).fetchone()
            if not hit:
                return cors({"error": "Appointment not found."}, 404)
            conn.execute(
                f"UPDATE doctor_appointments SET {', '.join(updates)} WHERE id = ? AND doctor_user_id = ?",
                tuple(params),
            )
            conn.commit()
        finally:
            conn.close()
        return cors({"status": "updated", "appointment_id": appointment_id})

    @app.route("/api/doctor/alerts", methods=["GET"])
    @auth_required("doctor")
    def doctor_alerts():
        conn = get_db()
        out = []
        try:
            rows = conn.execute(
                """SELECT d.report_id, d.risk_level, d.master_probability, d.created_at, p.owner_user_id
                   FROM diagnoses d
                   JOIN profiles p ON p.id = d.profile_id
                   WHERE upper(ifnull(d.risk_level,'')) IN ('HIGH', 'CRITICAL')
                   ORDER BY d.id DESC LIMIT 30"""
            ).fetchall()
            for r in rows:
                out.append(
                    {
                        "type": "AI_RISK_ALERT",
                        "patient_user_id": r["owner_user_id"],
                        "report_id": r["report_id"],
                        "risk_level": r["risk_level"],
                        "master_probability": r["master_probability"],
                        "created_at": r["created_at"],
                        "message": f"High-risk AI case detected ({r['risk_level']}).",
                    }
                )
        finally:
            conn.close()
        return cors(out)

    @app.route("/api/doctor/messages/<patient_user_id>", methods=["GET", "POST"])
    @auth_required("doctor")
    def doctor_messages(patient_user_id):
        doctor_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            p = conn.execute(
                "SELECT id FROM users WHERE user_id = ? AND role = 'patient'",
                (patient_user_id,),
            ).fetchone()
            if not p:
                return cors({"error": "Patient not found."}, 404)
            if request.method == "POST":
                body = request.get_json(force=True) or {}
                text = str(body.get("message_text", "")).strip()
                attachment_url = str(body.get("attachment_url", "")).strip()
                if not text:
                    return cors({"error": "message_text is required."}, 400)
                created_at = datetime.now().isoformat()
                cur = conn.execute(
                    """INSERT INTO doctor_messages
                       (doctor_user_id, patient_user_id, sender_role, message_text, attachment_url, created_at)
                       VALUES (?, ?, 'doctor', ?, ?, ?)""",
                    (doctor_user_id, patient_user_id, text, attachment_url, created_at),
                )
                conn.commit()
                return cors(
                    {
                        "id": cur.lastrowid,
                        "doctor_user_id": doctor_user_id,
                        "patient_user_id": patient_user_id,
                        "sender_role": "doctor",
                        "message_text": text,
                        "attachment_url": attachment_url,
                        "created_at": created_at,
                    },
                    201,
                )
            rows = conn.execute(
                """SELECT id, doctor_user_id, patient_user_id, sender_role, message_text, attachment_url, created_at
                   FROM doctor_messages
                   WHERE doctor_user_id = ? AND patient_user_id = ?
                   ORDER BY id DESC LIMIT 100""",
                (doctor_user_id, patient_user_id),
            ).fetchall()
            return cors(list(reversed([dict(r) for r in rows])))
        finally:
            conn.close()

    @app.route("/api/doctor/notes", methods=["POST"])
    @auth_required("doctor")
    def doctor_add_note():
        body = request.get_json(force=True) or {}
        patient_user_id = str(body.get("patient_user_id", "")).strip()
        prescription = str(body.get("prescription", "")).strip()
        remarks = str(body.get("remarks", "")).strip()
        ecg_signal_raw = body.get("ecg_signal")
        ecg_signal = []
        if isinstance(ecg_signal_raw, list):
            for v in ecg_signal_raw[:1200]:
                try:
                    ecg_signal.append(float(v))
                except Exception:
                    continue
        if not patient_user_id:
            return cors({"error": "patient_user_id is required."}, 400)
        if not prescription and not remarks:
            return cors({"error": "Provide prescription or remarks."}, 400)

        conn = get_db()
        try:
            p = conn.execute("SELECT id FROM users WHERE user_id = ? AND role = 'patient'", (patient_user_id,)).fetchone()
            if not p:
                return cors({"error": "Patient not found."}, 404)
            created_at = datetime.now().isoformat()
            cur = conn.execute(
                """INSERT INTO doctor_notes (doctor_user_id, patient_user_id, prescription, remarks, ecg_signal_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    request.current_user["user_id"],
                    patient_user_id,
                    prescription,
                    remarks,
                    json.dumps(ecg_signal) if ecg_signal else None,
                    created_at,
                ),
            )
            conn.commit()
            nid = cur.lastrowid
        finally:
            conn.close()
        return cors(
            {
                "id": nid,
                "doctor_user_id": request.current_user["user_id"],
                "patient_user_id": patient_user_id,
                "prescription": prescription,
                "remarks": remarks,
                "ecg_signal": ecg_signal,
                "created_at": created_at,
            },
            201,
        )

    @app.route("/api/doctor/notes/<int:note_id>", methods=["DELETE"])
    @auth_required("doctor")
    def doctor_delete_note(note_id):
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id FROM doctor_notes WHERE id = ? AND doctor_user_id = ?",
                (note_id, request.current_user["user_id"]),
            ).fetchone()
            if not row:
                return cors({"error": "Note not found."}, 404)
            conn.execute("DELETE FROM doctor_notes WHERE id = ?", (note_id,))
            conn.commit()
        finally:
            conn.close()
        return cors({"status": "deleted", "note_id": note_id})

    @app.route("/api/patient/doctor-summaries", methods=["GET"])
    @auth_required("patient")
    def patient_doctor_summaries():
        patient_user_id = request.current_user["user_id"]
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT id, doctor_user_id, prescription, remarks, ecg_signal_json, created_at
                   FROM doctor_notes
                   WHERE patient_user_id = ?
                   ORDER BY id DESC""",
                (patient_user_id,),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            item = dict(r)
            ecg = []
            try:
                raw = item.get("ecg_signal_json")
                if raw:
                    decoded = json.loads(raw)
                    if isinstance(decoded, list):
                        ecg = [float(x) for x in decoded if isinstance(x, (int, float))]
            except Exception:
                ecg = []
            item["ecg_signal"] = ecg
            item.pop("ecg_signal_json", None)
            out.append(item)
        return cors(out)
