AGRO MIRAI admin dashboard (React + Vite, Module 50 -- write-capable).

Calls the backend's /v2/admin/* routes (farmers/fields/bug-reports CRUD,
feedback, audit-log, an SSE bug-report stream) plus POST /admin/login,
POST /admin/logout. Vite is built with base: "./" (relative asset paths)
so the same bundle works both unprefixed at agromirai-admin.vercel.app/
and prefixed at agromirai.vercel.app/admin/* (see web/landing/vercel.json's
reverse-proxy rewrite).

Same-origin setup: the host forwards /admin/*, /v2/* and /health to the
Flask backend, so the session cookie is first-party.
  - Local dev: npm install && npm run dev (http://localhost:3100), proxies
    /admin, /v2, /health to BACKEND_URL (defaults to the live Render backend;
    override with BACKEND_URL=http://localhost:5000 for a local Flask server).
  - Vercel: vercel.json forwards to the Render backend (agro-mirai.onrender.com)
    plus a SPA-fallback rewrite for client-side routing. Build: npm run build
    (outputs to dist/). Deploy with: vercel deploy --prod

Backend must run with a cookie that survives this setup: FLASK_ENV=production
(Secure cookie, https) or, for plain http local testing, SESSION_COOKIE_SAMESITE=Lax.

The backend needs an admin account (role=admin), see MANUAL_TEST_GUIDE.md step 8.
