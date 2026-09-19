AGRO MIRAI admin dashboard (plain HTML/CSS/JS, read-only).

It calls the existing backend routes only: POST /admin/login, POST /admin/logout,
GET /v2/admin/farmers, /v2/admin/fields, /v2/admin/feedback.

Same-origin setup: the host forwards /admin/*, /v2/* and /health to the Flask
backend, so the session cookie is first-party.
  - Local:  BACKEND_URL=http://localhost:5000 node dev-server.mjs   (http://localhost:3100)
  - Vercel: replace BACKEND_HOST in vercel.json with the backend's public host, then
            vercel deploy --prod

Backend must run with a cookie that survives this setup: FLASK_ENV=production
(Secure cookie, https) or, for plain http local testing, SESSION_COOKIE_SAMESITE=Lax.

The backend needs an admin account (role=admin), see MANUAL_TEST_GUIDE.md step 8.
