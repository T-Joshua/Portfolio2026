# Contact form backend

The Flask app serves the portfolio and accepts contact form submissions at
`POST /api/contact`. Valid messages are stored in SQLite and emailed to the
configured contact address.

## Run locally

From the `backend` directory:

```powershell
python -m venv penv
.\penv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your Resend API key, verified sender address, and recipient
address. Keep real credentials only in `.env`; never put them in `.env.example`
or commit them. Verify the sender domain/address with Resend before sending.
Generate a persistent signing secret and add it as `SECRET_KEY` (required for a
stable CSRF token key across server restarts):

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Set `PUBLIC_ORIGIN` to the exact public site origin (for example
`https://portfolio.example.com`) and `ALLOWED_HOSTS` to its hostname. For local
development, leave both blank. If the site is served behind a TLS-terminating
proxy, configure that proxy and `PUBLIC_ORIGIN` correctly; do not trust arbitrary
forwarded headers from the internet.

```powershell
python app.py
```

Open `http://127.0.0.1:5000` to use the portfolio and submit a test message.
Submissions are saved to `backend/contact_messages.db` even if email delivery
is unavailable; the form reports when the email notification was not sent.
If email delivery fails, inspect the Flask terminal output for the Resend error.
Do not share or paste `.env` contents; share only the error text with credentials
and message content removed.

## Security behavior and deployment

- The contact endpoint requires a signed, expiring CSRF token and a matching
  same-origin `Origin` header.
- Contact submissions are limited to five per IP address per hour. The IP is
  stored as a keyed hash for rate limiting, not as a raw address. Behind a
  reverse proxy, configure trusted proxy handling at the server boundary before
  relying on IP-based limits.
- A hidden honeypot, server-side field validation, and a 16 KB request limit
  reduce automated and oversized submissions.
- Responses set a Content Security Policy and common browser security headers.
  The current Tailwind CDN requires `unsafe-eval`; for a stricter production CSP,
  build Tailwind CSS locally and remove that CDN allowance.
- Use HTTPS for any public deployment, set a persistent `SECRET_KEY`, and
  configure `PUBLIC_ORIGIN` and `ALLOWED_HOSTS`. Flask's built-in development
  server is for local development only; deploy behind a production WSGI server.

## Tests

Run from the `backend` directory with the environment activated:

```powershell
python -m unittest -v
```
