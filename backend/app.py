import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
import requests
import resend


BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
load_dotenv(BACKEND_DIR / ".env")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIELD_LIMITS = {
    "name": 120,
    "email": 254,
    "subject": 200,
    "message": 5000,
}


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR),
        static_folder=str(FRONTEND_DIR),
        static_url_path="",
    )
    trusted_hosts = [
        host.strip()
        for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    app.config.from_mapping(
        SECRET_KEY=SECRET_KEY,
        DATABASE=os.environ.get(
            "CONTACT_DATABASE", str(BACKEND_DIR / "contact_messages.db")
        ),
        MAX_CONTENT_LENGTH=16 * 1024,
        PUBLIC_ORIGIN=os.environ.get("PUBLIC_ORIGIN", "").rstrip("/"),
        TRUSTED_HOSTS=trusted_hosts or None,
        CSRF_TOKEN_MAX_AGE=2 * 60 * 60,
        CONTACT_RATE_LIMIT=5,
        CONTACT_RATE_WINDOW=60 * 60,
        RESEND_API_KEY=os.environ.get("RESEND_API_KEY", ""),
        RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL", ""),
        CONTACT_EMAIL=os.environ.get("CONTACT_EMAIL", ""),
    )
    if test_config:
        app.config.update(test_config)

    initialize_database(app.config["DATABASE"])
    csrf_serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"], salt="portfolio-contact-csrf"
    )
    if not os.environ.get("SECRET_KEY") and not (test_config and test_config.get("SECRET_KEY")):
        app.logger.warning(
            "SECRET_KEY is not configured; generated CSRF tokens will be invalidated on restart."
        )

    @app.before_request
    def set_content_security_nonce():
        g.csp_nonce = secrets.token_urlsafe(18)

    @app.after_request
    def add_security_headers(response):
        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "; ".join(
                (
                    "default-src 'self'",
                    "base-uri 'self'",
                    "object-src 'none'",
                    "frame-ancestors 'none'",
                    "form-action 'self'",
                    f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval' https://cdn.tailwindcss.com",
                    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.tailwindcss.com",
                    "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com",
                    "img-src 'self' data: https://images.unsplash.com",
                    "connect-src 'self'",
                )
            ),
        )
        public_origin = app.config["PUBLIC_ORIGIN"]
        if request.is_secure or public_origin.lower().startswith("https://"):
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000"
            )
        return response
    
    @app.route('/health', methods=['GET'])
    def health_check():
        return "OK", 200

    @app.get("/")
    @app.get("/index.html")
    def index():
        response = app.make_response(
            render_template(
                "index.html",
                csrf_token=csrf_serializer.dumps(secrets.token_urlsafe(32)),
                csp_nonce=g.csp_nonce,
            )
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/contact")
    def submit_contact():
        if not request_has_valid_origin(app.config["PUBLIC_ORIGIN"]):
            return jsonify(error="Request origin is not allowed."), 403

        csrf_token = request.headers.get("X-CSRF-Token", "")
        try:
            csrf_serializer.loads(
                csrf_token, max_age=app.config["CSRF_TOKEN_MAX_AGE"]
            )
        except (BadSignature, TypeError):
            return jsonify(error="Form security token is invalid or expired. Reload the page and try again."), 403

        if not request.is_json:
            return jsonify(error="Request body must be JSON."), 415

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Request body must be a JSON object."), 400

        honeypot_value = payload.get("website", "")
        if not isinstance(honeypot_value, str) or honeypot_value.strip():
            return jsonify(error="Invalid form submission."), 400

        allowed, retry_after = allow_contact_submission(
            app.config["DATABASE"],
            request.remote_addr or "unknown",
            app.config["SECRET_KEY"],
            app.config["CONTACT_RATE_LIMIT"],
            app.config["CONTACT_RATE_WINDOW"],
        )
        if not allowed:
            response = jsonify(
                error="Too many messages were submitted. Please try again later."
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        contact, error = validate_contact(payload)
        if error:
            return jsonify(error=error), 400

        try:
            save_contact(app.config["DATABASE"], contact)
        except sqlite3.Error:
            app.logger.exception("Unable to save contact submission.")
            return jsonify(error="Unable to save your message. Please try again later."), 500

        try:
            send_contact_email(app.config, contact)
        except (resend.exceptions.ResendError, requests.exceptions.RequestException, ValueError):
            app.logger.exception("Email delivery failed.")
            return jsonify(
                message="Your message was saved, but the email notification could not be sent.",
                email_sent=False,
            ), 202

        return jsonify(
            message="Thanks! Your message has been sent successfully.",
            email_sent=True,
        ), 201

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(error="Message is too large. Please shorten it and try again."), 413

    @app.errorhandler(400)
    def invalid_request(_error):
        return jsonify(error="Invalid request."), 400

    return app


def initialize_database(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS contact_rate_limits (
                    ip_hash TEXT NOT NULL,
                    window_start INTEGER NOT NULL,
                    request_count INTEGER NOT NULL,
                    PRIMARY KEY (ip_hash, window_start)
                )
                """
            )


def request_has_valid_origin(public_origin):
    origin = request.headers.get("Origin")
    if not origin:
        return False

    expected_origin = public_origin or request.host_url.rstrip("/")
    try:
        provided = urlsplit(origin)
        expected = urlsplit(expected_origin)
        provided_port = provided.port or (443 if provided.scheme.lower() == "https" else 80)
        expected_port = expected.port or (443 if expected.scheme.lower() == "https" else 80)
        return (
            provided.scheme.lower() in ("http", "https")
            and provided.hostname is not None
            and provided.path == ""
            and not provided.query
            and not provided.fragment
            and not provided.username
            and not provided.password
            and provided.scheme.lower() == expected.scheme.lower()
            and provided.hostname.lower() == (expected.hostname or "").lower()
            and provided_port == expected_port
        )
    except ValueError:
        return False


def allow_contact_submission(database_path, remote_address, secret_key, limit, window):
    now = int(time.time())
    window_start = now - now % window
    ip_hash = hmac.new(
        secret_key.encode("utf-8"),
        remote_address.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    with closing(sqlite3.connect(database_path, timeout=5)) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM contact_rate_limits WHERE window_start < ?",
                (window_start - window,),
            )
            connection.execute(
                """
                INSERT INTO contact_rate_limits (ip_hash, window_start, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT (ip_hash, window_start)
                DO UPDATE SET request_count = request_count + 1
                """,
                (ip_hash, window_start),
            )
            request_count = connection.execute(
                """
                SELECT request_count FROM contact_rate_limits
                WHERE ip_hash = ? AND window_start = ?
                """,
                (ip_hash, window_start),
            ).fetchone()[0]

    retry_after = max(1, window_start + window - now)
    return request_count <= limit, retry_after


def validate_contact(payload):
    contact = {}
    for field, limit in FIELD_LIMITS.items():
        value = payload.get(field)
        if not isinstance(value, str):
            return None, f"Please provide a valid {field}."
        value = value.strip()
        if not value:
            return None, f"Please provide a {field}."
        if len(value) > limit:
            return None, f"{field.capitalize()} must be {limit} characters or fewer."
        if field != "message" and any(char in value for char in "\r\n"):
            return None, f"Please provide a valid {field}."
        if field == "message" and "\x00" in value:
            return None, "Please provide a valid message."
        contact[field] = value

    if not EMAIL_PATTERN.fullmatch(contact["email"]):
        return None, "Please provide a valid email address."
    return contact, None


def save_contact(database_path, contact):
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO contact_messages (name, email, subject, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    contact["name"],
                    contact["email"],
                    contact["subject"],
                    contact["message"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


def send_contact_email(config, contact):
    api_key = config["RESEND_API_KEY"]
    from_email = config["RESEND_FROM_EMAIL"]
    if not api_key or not from_email or not config["CONTACT_EMAIL"]:
        raise ValueError("Resend email configuration is incomplete.")

    resend.api_key = api_key

    escaped_name = html.escape(contact["name"])
    escaped_email = html.escape(contact["email"])
    escaped_subject = html.escape(contact["subject"])
    escaped_message = html.escape(contact["message"]).replace("\n", "<br>")
    params = {
        "from": from_email,
        "to": [config["CONTACT_EMAIL"]],
        "subject": f"Portfolio Inquiry: {contact['subject']}",
        "reply_to": contact["email"],
        "html": f"""
            <div style="font-family: sans-serif; padding: 20px; color: #333;">
                <h2 style="color: #3b82f6;">New Message from Your Portfolio</h2>
                <p><strong>Name:</strong> {escaped_name}</p>
                <p><strong>Email:</strong> {escaped_email}</p>
                <p><strong>Subject:</strong> {escaped_subject}</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p><strong>Message:</strong></p>
                <p style="background: #f9fafb; padding: 15px; border-radius: 6px; line-height: 1.5;">{escaped_message}</p>
            </div>
        """
    }
    
    return resend.Emails.send(params)


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")