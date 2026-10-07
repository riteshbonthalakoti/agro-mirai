# Admin Dashboard Redesign — Design Spec
**Date:** 2026-10-08  
**Module:** 54  
**Status:** Approved for implementation

---

## 1. Goal

Replace the current plain-HTML admin SPA (`web/admin/`) with a polished, professional dashboard using Tailwind CSS (CDN) + Alpine.js (CDN). No build step. No framework. All existing `/v2/admin/*` JSON API routes remain unchanged.

---

## 2. Scope

### In scope
- `web/admin/index.html` — SPA shell
- `web/admin/admin.js` — application logic (full rewrite, same feature parity + improvements)
- `web/admin/style.css` — replaced by Tailwind utilities; file kept for minor custom overrides only
- All 7 views: Login, Overview, Farmers, Fields, Bug Reports, Audit Log, OTPs
- Responsive layout for laptop screens (≥1024px); usable on tablet

### Out of scope
- Flask backend routes — no changes
- Server-rendered Jinja2 templates (`admin_dashboard.html`, `admin_login.html`) — kept as fallback, not touched
- Mobile app
- Landing page

---

## 3. Technology

| Dependency | Source | Version pin |
|------------|--------|-------------|
| Tailwind CSS | CDN (`cdn.tailwindcss.com`) | latest |
| Alpine.js | CDN (`cdn.jsdelivr.net/npm/alpinejs`) | `@3.x.x/dist/cdn.min.js` |
| Chart.js | CDN (`cdn.jsdelivr.net/npm/chart.js`) | `@4.x.x` |

No npm, no bundler, no TypeScript. All JS in `admin.js` as plain ES2020 modules pattern (IIFE or top-level `Alpine.data` registrations).

---

## 4. Layout & Visual Design

### Shell
```
┌─────────────────────────────────────────────────┐
│ Sidebar (220px fixed) │ Content area (flex-1)   │
│                       │                          │
│  🌿 AGRO MIRAI ADMIN  │  [Page title]  [Actions] │
│  ─────────────────    │  ─────────────────────── │
│  □ Overview           │                          │
│  □ Farmers            │   <page content>         │
│  □ Fields             │                          │
│  □ Bug Reports  [●3]  │                          │
│  □ Audit Log          │                          │
│  □ OTPs (dev)         │                          │
│  ─────────────────    │                          │
│  [Logout]             │                          │
└─────────────────────────────────────────────────┘
```

### Color tokens (defined as Tailwind `theme.extend` in inline config)
| Token | Value | Usage |
|-------|-------|-------|
| `sidebar` | `#0f1117` | Sidebar background |
| `sidebar-hover` | `#1a1f2e` | Sidebar item hover |
| `accent` | `#22c55e` | Active nav, primary buttons, badges |
| `surface` | `#f8fafc` | Content background |
| `card` | `#ffffff` | Stat cards, table container |

### Typography
- Font: system-ui stack (no Google Fonts fetch)
- Sidebar text: `text-slate-300`, active: `text-white`
- Content headings: `text-slate-800`
- Table text: `text-slate-700 text-sm`

---

## 5. Pages

### 5.1 Login
- Centered card on dark full-screen background (`#0f1117`)
- Logo mark + "AGRO MIRAI Admin" heading
- Email + password fields with Tailwind styling
- Single "Sign in" button (accent green)
- Error message slot (red banner, shown on 401)
- On success: calls `POST /admin/login`, detects redirect to `/admin`, then loads the SPA shell

### 5.2 Overview
Six stat cards in a 3-col grid:

| Card | API source |
|------|-----------|
| Total Farmers | `overview.farmer_count` |
| Total Fields | `overview.field_count` |
| Disease Scans | `overview.scan_count` |
| Advisories | `overview.advisory_count` |
| Open Bugs | `overview.open_bug_count` |
| Avg Feedback | `overview.avg_feedback_rating` |

Two bar charts (Chart.js):
- **Crop distribution** — horizontal bars, top 8 crops
- **Language distribution** — horizontal bars, all 4 languages

**Recent activity feed** — last 20 events from `overview.recent_activity`, shown as a timeline list with icon, action text, timestamp.

### 5.3 Farmers
- Full-width table: Name, Phone, Language, District, Fields count, Joined, Actions
- Row actions: Edit (pencil icon) → opens right-side edit drawer; Delete (trash icon) → type-to-confirm modal
- Edit drawer fields: name, preferred_language (select), phone, district, state
- Calls `PATCH /v2/admin/farmers/<id>` on save
- Delete calls `DELETE /v2/admin/farmers/<id>` after confirm
- Clicking a row name navigates to Farmer Detail view

### 5.4 Farmer Detail (sub-view of Farmers)
- Breadcrumb: Farmers > {name}
- Three tabs: Fields, Scans, Advisories — filtered to this farmer
- Fields tab: same table as global fields but scoped
- Scans tab: date, disease, confidence, source badge (CNN vs environmental)
- Advisories tab: date, title, severity badge, first 100 chars of body

### 5.5 Fields
- Table: Field name, Farmer, Crop, Soil type, Area, Lat/Lng, Actions
- Edit drawer: name, latitude, longitude, area_ha, elevation_m, soil_type (select from enum), current_crop, sown_on (date)
- Delete with type-to-confirm

### 5.6 Bug Reports
**Layout:** Status board with four column cards (Kanban-lite):
- Open | Triaged | In Progress | Resolved

Each card shows count badge. Clicking a status column shows the filtered list below.

Alternatively (simpler): single table with status badge pills and a quick inline status dropdown on each row.

**Decision:** Table layout (matches existing data density, easier to scan). Status shown as colored badge pill; quick-change via a `<select>` dropdown in the row. Calls `PATCH /v2/admin/bug-reports/<id>` with `{status}`.

Delete button with confirm modal.

**Live badge:** Bug Reports nav item shows a red dot + count when new reports arrive via SSE (`/v2/admin/stream/bug-reports`). Badge resets when user visits the view.

### 5.7 Audit Log
- Read-only table: Timestamp, Admin, Action, Target type, Target ID, Before/After (collapsible JSON diff)
- "Before/After" column: shows a `▶` toggle that expands an inline pre-formatted JSON block
- No write actions

### 5.8 OTPs
- Shown only when `overview.otp_dev_mode === true`
- Table: Phone, OTP, Expires at
- Nav item hidden in production

---

## 6. Components (Alpine.js `x-data`)

| Component | Description |
|-----------|-------------|
| `appShell` | Top-level state: `currentView`, `farmer` (selected for detail), `unreadBugs`, SSE connection |
| `overviewPage` | Fetches + holds overview data, initializes Chart.js instances |
| `farmersPage` | Fetches farmers list, manages edit drawer state, delete confirm state |
| `fieldsPage` | Same pattern as farmersPage |
| `bugReportsPage` | Fetches bug reports, status-patch handler, SSE badge update |
| `auditLogPage` | Fetches audit log, manages row expand state |
| `editDrawer` | Reusable slide-in drawer: `open`, `record`, `schema`, `onSave` |
| `confirmModal` | Type-to-confirm delete: `open`, `confirmText`, `expected`, `onConfirm` |

---

## 7. State Management

All state lives in Alpine `x-data` components. No global singleton. Components fetch on `x-init`. The shell component (`appShell`) holds cross-cutting state:
- `currentView: string` — drives nav active state and `x-show` on page containers
- `authUser: object | null`
- `unreadBugs: number` — incremented by SSE, reset on navigating to Bug Reports

---

## 8. API Integration

No changes to the API. All calls from `admin.js` match existing endpoints. Auth continues via session cookie (browser sends automatically). Login flow unchanged: POST to `/admin/login`, detect redirect.

Error handling: all fetch calls check `resp.ok`; on 401 redirect to login view; on other errors show a toast notification (top-right, auto-dismisses after 4s).

---

## 9. Files Changed

| File | Change |
|------|--------|
| `web/admin/index.html` | Full rewrite — Tailwind/Alpine CDN links, SPA shell markup |
| `web/admin/admin.js` | Full rewrite — Alpine `x-data` components, same API calls |
| `web/admin/style.css` | Trimmed to ~20 lines of custom overrides (scrollbars, chart canvas sizing) |
| `web/admin/vercel.json` | No change |
| `web/admin/dev-server.mjs` | No change |

Server-side files: **no changes**.

---

## 10. Testing

- Manual smoke test: login → overview loads charts → edit a farmer → delete a field → change bug status → check audit log entry appears
- Existing backend tests (`tests/api/test_admin_*.py`) all pass unchanged (no API changes)
- No new test files required (UI-only change)

---

## 11. Deployment

Same Vercel project. `git push` to main triggers redeploy. No env var changes.

---

## 12. Out-of-scope follow-ups (not in this spec)

- Admin password change UI
- Multi-admin accounts
- CSV export of tables
- Home tab redesign (separate spec)
