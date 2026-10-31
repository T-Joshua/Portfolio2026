import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import requests

from app import create_app


class ContactApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp_dir.name) / "contacts.db")
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.database,
                "SECRET_KEY": "test-secret-key",
                "PUBLIC_ORIGIN": "http://localhost",
                "RESEND_API_KEY": "test-api-key",
                "RESEND_FROM_EMAIL": "Portfolio <portfolio@example.com>",
                "CONTACT_EMAIL": "owner@example.com",
            }
        )
        self.client = self.app.test_client()
        self.payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Project inquiry",
            "message": "I would like to discuss a project.",
        }
        response = self.client.get("/")
        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)">',
            response.data,
        )
        self.assertIsNotNone(match)
        self.csrf_token = match.group(1).decode("ascii")
        response.close()

    def post_contact(self, payload=None, origin="http://localhost", csrf_token=None):
        headers = {"Origin": origin}
        headers["X-CSRF-Token"] = (
            self.csrf_token if csrf_token is None else csrf_token
        )
        return self.client.post(
            "/api/contact",
            json=payload if payload is not None else self.payload,
            headers=headers,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_homepage_serves_the_contact_form(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="contact-form"', response.data)
        self.assertIn(b'name="csrf-token"', response.data)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        nonce = re.search(rb'<script nonce="([^"]+)">', response.data).group(1).decode()
        self.assertIn(
            f"'nonce-{nonce}'",
            response.headers["Content-Security-Policy"],
        )
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        response.close()

    def test_index_html_route_renders_csrf_token(self):
        response = self.client.get("/index.html")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data, rb'name="csrf-token" content="[^"]+"')
        response.close()

    @patch("app.resend.Emails.send")
    def test_valid_submission_is_saved_and_emailed(self, email_send):
        response = self.post_contact()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["email_sent"])
        email_send.assert_called_once()
        mail_data = email_send.call_args.args[0]
        self.assertEqual(mail_data["to"], ["owner@example.com"])
        self.assertIn("Jane Doe", mail_data["html"])
        with closing(sqlite3.connect(self.database)) as connection:
            saved = connection.execute(
                "SELECT name, email, subject, message FROM contact_messages"
            ).fetchone()
        self.assertEqual(saved, tuple(self.payload.values()))

    @patch("app.resend.Emails.send")
    def test_invalid_email_is_rejected_without_saving_or_emailing(self, email_send):
        self.payload["email"] = "not-an-email"

        response = self.post_contact()

        self.assertEqual(response.status_code, 400)
        email_send.assert_not_called()
        with closing(sqlite3.connect(self.database)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM contact_messages"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    @patch("app.resend.Emails.send")
    def test_submission_is_saved_when_email_delivery_fails(self, email_send):
        email_send.side_effect = requests.exceptions.ConnectionError(
            "Email provider unavailable"
        )

        with self.assertLogs("app", level="ERROR"):
            response = self.post_contact()

        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.json["email_sent"])
        self.assertNotIn("Email provider unavailable", response.get_data(as_text=True))
        with closing(sqlite3.connect(self.database)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM contact_messages"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_non_json_request_is_rejected(self):
        response = self.client.post(
            "/api/contact",
            data="name=Jane",
            headers={
                "Origin": "http://localhost",
                "X-CSRF-Token": self.csrf_token,
            },
        )

        self.assertEqual(response.status_code, 415)

    def test_missing_csrf_token_is_rejected(self):
        response = self.post_contact(csrf_token="")

        self.assertEqual(response.status_code, 403)
        self.assertIn("security token", response.json["error"])

    def test_cross_origin_request_is_rejected(self):
        response = self.post_contact(origin="https://attacker.example")

        self.assertEqual(response.status_code, 403)
        self.assertIn("origin", response.json["error"])

    def test_missing_origin_is_rejected(self):
        response = self.client.post(
            "/api/contact",
            json=self.payload,
            headers={"X-CSRF-Token": self.csrf_token},
        )

        self.assertEqual(response.status_code, 403)

    @patch("app.resend.Emails.send")
    def test_configured_public_origin_is_accepted_and_sets_hsts(self, _email_send):
        self.app.config["PUBLIC_ORIGIN"] = "https://portfolio.example"
        response = self.client.get("/")
        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=31536000",
        )
        response.close()

        response = self.post_contact(origin="https://portfolio.example")

        self.assertEqual(response.status_code, 201)

    @patch("app.resend.Emails.send")
    def test_honeypot_submission_is_rejected_without_saving(self, email_send):
        payload = {**self.payload, "website": "spam"}

        response = self.post_contact(payload=payload)

        self.assertEqual(response.status_code, 400)
        email_send.assert_not_called()
        with closing(sqlite3.connect(self.database)) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM contact_messages"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    @patch("app.resend.Emails.send")
    def test_contact_endpoint_is_rate_limited(self, email_send):
        self.app.config["CONTACT_RATE_LIMIT"] = 2
        self.post_contact()
        self.post_contact()

        response = self.post_contact()

        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers["Retry-After"]), 0)
        self.assertEqual(email_send.call_count, 2)

    def test_expired_csrf_token_is_rejected(self):
        self.app.config["CSRF_TOKEN_MAX_AGE"] = -1

        response = self.post_contact()

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
