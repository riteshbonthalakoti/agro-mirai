AGRO MIRAI admin dashboard (plain HTML/CSS/JS, read-only).

It calls the existing backend routes only: POST /admin/login, POST /admin/logout,
GET /v2/admin/farmers, /v2/admin/fields, /v2/admin/feedback.

Same-origin setup: the host forwards /admin/*, /v2/* and /health to the Flask
backend, so the session cookie is first-party.
  - Local:  BACKEND_URL=http://localhost:5000 node dev-server.mjs   (http://localhost:3100)
  - Vercel: vercel.json forwards to the Render backend (agro-mirai.onrender.com), so the
            dashboard works with the laptop off. Module 40: voice now runs via Sarvam AI's
            hosted API (no local/Oracle service needed) and the leaf-disease CNN has its own
            second free Render service (agro-mirai-cnn.onrender.com, ONNX Runtime) -- see
            decisions/0025-onnx-cnn-service.md. Everything the app needs is cloud-hosted.
            Deploy with: vercel deploy --prod

Backend must run with a cookie that survives this setup: FLASK_ENV=production
(Secure cookie, https) or, for plain http local testing, SESSION_COOKIE_SAMESITE=Lax.

The backend needs an admin account (role=admin), see MANUAL_TEST_GUIDE.md step 8.

