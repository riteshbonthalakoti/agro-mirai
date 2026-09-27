AGRO MIRAI admin dashboard (plain HTML/CSS/JS, Module 50 -- write-capable).

The original read-only design (Overview stat cards + bar charts, Farmers
list/detail) plus write actions added on top: farmer edit/delete, field
edit/delete, a Bug Reports tab (live via SSE, status dropdown + delete),
and an Audit Log tab. No build step, no framework -- kept intentionally
plain to match the visual style everyone actually liked.

It calls: POST /admin/login, POST /admin/logout, GET /v2/admin/{farmers,
fields,feedback,scans,advisories,bug-reports,audit-log}, PATCH/DELETE on
/v2/admin/farmers/{id} and /v2/admin/fields/{id}, PATCH/DELETE on
/v2/admin/bug-reports/{id}, and an SSE stream at
GET /v2/admin/stream/bug-reports.

Same-origin setup: the host forwards /admin/*, /v2/* and /health to the
Flask backend, so the session cookie is first-party.
  - Local:  BACKEND_URL=http://localhost:5000 node dev-server.mjs   (http://localhost:3100)
  - Vercel: vercel.json forwards to the Render backend (agro-mirai.onrender.com).
            Deploy with: vercel deploy --prod (or push to main -- the
            CD pipeline in .github/workflows/deploy.yml auto-deploys
            after CI passes; see docs/TOOLING.md's "CI/CD (Module 50)"
            section).

Reachable at two public URLs, same deployment: agromirai-admin.vercel.app/
(root) and agromirai.vercel.app/admin/* (reverse-proxied via
web/landing/vercel.json, which forwards style.css/admin.js/favicon.ico
explicitly by name since this is a plain static site with stable
filenames, not a hashed build).

Backend must run with a cookie that survives this setup: FLASK_ENV=production
(Secure cookie, https) or, for plain http local testing, SESSION_COOKIE_SAMESITE=Lax.

The backend needs an admin account (role=admin), see MANUAL_TEST_GUIDE.md step 8.
