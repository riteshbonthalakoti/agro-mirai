# Admin Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `web/admin/` as a polished Tailwind CSS + Alpine.js SPA with 7 views (Login, Overview, Farmers, Fields, Bug Reports, Audit Log, OTPs), preserving all existing `/v2/admin/*` API calls and feature parity.

**Architecture:** Single-page app; all state lives in Alpine `x-data` components registered in `admin.js`. `index.html` contains the full markup skeleton with `x-show`/`x-data` per page section. `style.css` shrinks to ~25 lines of custom overrides (chart canvas sizing, custom scrollbar).

**Tech Stack:** Tailwind CSS (CDN), Alpine.js 3.x (CDN), Chart.js 4.x (CDN), vanilla ES2020, no build step.

**Spec:** `docs/superpowers/specs/2026-10-08-admin-dashboard-redesign.md`

---

## Global Constraints

- No npm, no bundler, no TypeScript — all JS in `admin.js` as plain ES2020
- All CDN loads: Tailwind `cdn.tailwindcss.com`, Alpine `cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js`, Chart.js `cdn.jsdelivr.net/npm/chart.js@4.x.x`
- No backend route changes — all API paths identical to current `admin.js`
- Login flow: POST to `/admin/login`, detect redirect to `/admin` path (existing mechanism, unchanged)
- Accent color `#22c55e` (green-500 in Tailwind), sidebar `#0f1117`, sidebar hover `#1a1f2e`
- No Google Fonts — system font stack only
- `web/admin/vercel.json` and `web/admin/dev-server.mjs` — no changes

---

## Review Focus

- **Login redirect detection on Safari/Firefox:** `new URL(r.url).pathname` must strip trailing slashes — test that `/admin/` (with slash) is treated as success, not an infinite loop.
- **SSE reconnect when backend cold-starts:** `EventSource` fires `onerror` on Render's 30-second cold start; the badge must show "reconnecting…" not crash.
- **Chart.js canvas reuse:** navigating away from Overview and back must destroy old Chart instances before creating new ones, or Chart.js throws "Canvas is already in use."
- **Alpine `x-show` vs `x-if` for OTP polling:** OTP interval must be cleared when the OTPs section is hidden, not just when the page unloads; use Alpine's `$watch` or `x-effect` for cleanup.
- **Confirm modal focus trap:** after the modal opens, focus must land on the text input (not the page behind), or users on keyboard-only setups will type into hidden fields.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `web/admin/index.html` | Full rewrite | CDN script/style tags, sidebar + content shell, all page containers with `x-data`/`x-show` |
| `web/admin/admin.js` | Full rewrite | All `Alpine.data(...)` registrations; api helper; no DOM manipulation outside Alpine |
| `web/admin/style.css` | Trim to overrides | Chart canvas `max-height`, custom scrollbar, `[x-cloak]` hide rule, JSON pre block |

---

## Task 1: CDN Shell + Login View

**Files:**
- Rewrite: `web/admin/index.html`
- Rewrite: `web/admin/style.css`

**Goal:** Replace bare HTML with Tailwind + Alpine CDN links and a polished login card. The rest of the page body is a placeholder `<div id="app">` that Task 2 fills in.

- [ ] **Step 1: Rewrite `index.html`**

Replace the entire file with:

```html
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AGRO MIRAI — Admin</title>
  <meta name="robots" content="noindex, nofollow">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            sidebar: '#0f1117',
            'sidebar-hover': '#1a1f2e',
            accent: '#22c55e',
          }
        }
      }
    }
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.x.x/dist/chart.umd.min.js"></script>
  <link rel="stylesheet" href="style.css">
</head>
<body class="h-full bg-slate-50 text-slate-800 font-sans" x-data="adminApp()" x-init="init()">

  <!-- LOGIN -->
  <div x-show="!authed" x-cloak
       class="min-h-screen flex items-center justify-center bg-sidebar px-4">
    <div class="w-full max-w-sm bg-white rounded-2xl shadow-xl p-8">
      <div class="flex items-center gap-3 mb-6">
        <span class="text-3xl">🌿</span>
        <div>
          <div class="font-bold text-lg leading-tight">AGRO MIRAI</div>
          <div class="text-xs text-slate-500">Admin Dashboard</div>
        </div>
      </div>
      <form @submit.prevent="login()">
        <label class="block mb-4">
          <span class="text-sm text-slate-600 font-medium">Email</span>
          <input x-model="loginEmail" type="email" required autocomplete="username"
                 class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
        </label>
        <label class="block mb-5">
          <span class="text-sm text-slate-600 font-medium">Password</span>
          <input x-model="loginPassword" type="password" required autocomplete="current-password"
                 class="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent">
        </label>
        <p x-show="loginError" x-text="loginError"
           class="text-red-600 text-sm mb-3 bg-red-50 rounded-lg px-3 py-2"></p>
        <button type="submit" :disabled="loginBusy"
                class="w-full bg-accent text-white font-semibold rounded-lg py-2.5 text-sm hover:bg-green-600 disabled:opacity-50 transition-colors">
          <span x-text="loginBusy ? 'Signing in…' : 'Sign in'"></span>
        </button>
      </form>
    </div>
  </div>

  <!-- APP SHELL -->
  <div x-show="authed" x-cloak class="flex h-screen overflow-hidden">

    <!-- Sidebar -->
    <aside class="w-56 flex-none bg-sidebar flex flex-col">
      <div class="px-5 py-5 border-b border-white/10">
        <div class="flex items-center gap-2">
          <span class="text-xl">🌿</span>
          <div>
            <div class="text-white text-sm font-semibold leading-tight">AGRO MIRAI</div>
            <div class="text-slate-400 text-xs">Admin</div>
          </div>
        </div>
      </div>
      <nav class="flex-1 py-3 space-y-0.5 px-2 overflow-y-auto">
        <template x-for="item in navItems" :key="item.view">
          <a :href="'#/' + item.hash"
             @click="navigate(item.view)"
             class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors"
             :class="view === item.view
               ? 'bg-accent/20 text-accent font-medium'
               : 'text-slate-400 hover:bg-sidebar-hover hover:text-white'"
             x-show="item.view !== 'otps' || otpDevMode">
            <span x-text="item.icon" class="text-base w-5 text-center"></span>
            <span x-text="item.label" class="flex-1"></span>
            <span x-show="item.view === 'bugs' && unreadBugs > 0"
                  x-text="unreadBugs"
                  class="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
            </span>
          </a>
        </template>
      </nav>
      <div class="p-3 border-t border-white/10">
        <button @click="logout()"
                class="w-full text-slate-400 hover:text-white text-sm py-2 px-3 rounded-lg hover:bg-sidebar-hover transition-colors text-left">
          ↩ Sign out
        </button>
      </div>
    </aside>

    <!-- Content -->
    <main class="flex-1 overflow-y-auto bg-slate-50">
      <!-- Toast -->
      <div x-show="toast.show" x-transition
           class="fixed top-4 right-4 z-50 rounded-xl shadow-lg px-4 py-3 text-sm font-medium"
           :class="toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-slate-800 text-white'">
        <span x-text="toast.msg"></span>
      </div>

      <!-- Confirm modal -->
      <div x-show="confirm.show" x-cloak
           class="fixed inset-0 bg-black/50 flex items-center justify-center z-40 px-4"
           @keydown.escape.window="confirm.show = false">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
          <h3 class="font-semibold text-slate-800 mb-2">Confirm deletion</h3>
          <p class="text-sm text-slate-600 mb-4">
            Type <strong x-text="confirm.expected"></strong> to permanently delete this. This cannot be undone.
          </p>
          <input x-model="confirm.typed" x-ref="confirmInput"
                 @keydown.enter="confirm.typed === confirm.expected && confirm.onConfirm()"
                 autocomplete="off"
                 class="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-red-400">
          <div class="flex gap-2 justify-end">
            <button @click="confirm.show = false"
                    class="px-4 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">Cancel</button>
            <button @click="confirm.onConfirm()"
                    :disabled="confirm.typed !== confirm.expected"
                    class="px-4 py-2 text-sm rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-40">Delete</button>
          </div>
        </div>
      </div>

      <!-- Edit drawer -->
      <div x-show="drawer.show" x-cloak
           class="fixed inset-0 bg-black/40 z-30 flex justify-end"
           @click.self="drawer.show = false">
        <div class="bg-white w-full max-w-md h-full overflow-y-auto shadow-2xl p-6"
             @keydown.escape.window="drawer.show = false">
          <div class="flex items-center justify-between mb-6">
            <h3 class="font-semibold text-slate-800" x-text="drawer.title"></h3>
            <button @click="drawer.show = false" class="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
          </div>
          <div x-html="drawer.bodyHtml"></div>
          <div class="flex gap-3 mt-6">
            <button @click="drawer.save()" :disabled="drawer.saving"
                    class="flex-1 bg-accent text-white font-semibold py-2.5 rounded-lg text-sm hover:bg-green-600 disabled:opacity-50">
              <span x-text="drawer.saving ? 'Saving…' : 'Save changes'"></span>
            </button>
            <button @click="drawer.show = false"
                    class="px-4 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">Cancel</button>
          </div>
          <p x-show="drawer.error" x-text="drawer.error" class="text-red-600 text-sm mt-3"></p>
        </div>
      </div>

      <!-- Page views (each section has its own x-data, shown based on shell view) -->
      <div x-show="view === 'overview'" x-data="overviewPage()" x-init="load()" class="p-6">
        <div class="mb-6"><h1 class="text-xl font-bold text-slate-800">Overview</h1></div>
        <template x-if="loading"><div class="text-slate-400 text-sm">Loading…</div></template>
        <template x-if="!loading">
          <div>
            <!-- Stat cards -->
            <div class="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              <template x-for="card in statCards" :key="card.label">
                <div class="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                  <div class="text-xs text-slate-500 font-medium mb-1" x-text="card.label"></div>
                  <div class="text-3xl font-bold text-accent" x-text="card.value"></div>
                  <div class="text-xs text-slate-400 mt-0.5" x-text="card.note" x-show="card.note"></div>
                </div>
              </template>
            </div>
            <!-- Charts row -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <div class="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                <div class="text-sm font-semibold text-slate-700 mb-3">Crop distribution</div>
                <canvas id="cropChart" class="chart-canvas"></canvas>
              </div>
              <div class="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                <div class="text-sm font-semibold text-slate-700 mb-3">Language distribution</div>
                <canvas id="langChart" class="chart-canvas"></canvas>
              </div>
            </div>
            <!-- Recent activity -->
            <div class="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
              <div class="text-sm font-semibold text-slate-700 mb-3">Recent activity</div>
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-100">
                    <th class="pb-2 pr-4">When</th><th class="pb-2 pr-4">Type</th>
                    <th class="pb-2 pr-4">Field</th><th class="pb-2">Detail</th>
                  </tr></thead>
                  <tbody>
                    <template x-for="row in recentActivity" :key="row.created_at + row.type">
                      <tr class="border-b border-slate-50 last:border-0">
                        <td class="py-2 pr-4 text-slate-500 whitespace-nowrap" x-text="row.when"></td>
                        <td class="py-2 pr-4">
                          <span class="px-2 py-0.5 rounded-full text-xs font-medium"
                                :class="row.type === 'Advisory' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'"
                                x-text="row.type"></span>
                        </td>
                        <td class="py-2 pr-4 text-slate-700" x-text="row.field_name"></td>
                        <td class="py-2 text-slate-500" x-text="row.detail"></td>
                      </tr>
                    </template>
                    <tr x-show="!recentActivity.length">
                      <td colspan="4" class="py-4 text-slate-400 text-sm">No activity yet.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div x-show="view === 'farmers'" x-data="farmersPage()" x-init="load()" class="p-6">
        <!-- farmer list & detail rendered by farmersPage component -->
        <template x-if="detailId">
          <div x-data="farmerDetailPage()" x-init="load(detailId)">
            <!-- breadcrumb -->
            <div class="mb-4">
              <button @click="$dispatch('nav-farmers-list')" class="text-accent text-sm hover:underline">← All farmers</button>
            </div>
            <template x-if="loading"><div class="text-slate-400 text-sm">Loading…</div></template>
            <template x-if="!loading">
              <div>
                <div class="flex items-center gap-3 mb-6">
                  <h1 class="text-xl font-bold text-slate-800" x-text="farmer.name"></h1>
                  <span class="px-2.5 py-0.5 rounded-full bg-green-50 text-accent text-xs font-medium" x-text="langName(farmer.preferred_language)"></span>
                </div>
                <!-- farmer edit card -->
                <div class="bg-white rounded-xl border border-slate-100 shadow-sm p-5 mb-6">
                  <div class="grid grid-cols-2 gap-4 mb-4">
                    <label class="block">
                      <span class="text-xs text-slate-500 font-medium">Name</span>
                      <input x-model="editForm.name" class="input-field mt-1">
                    </label>
                    <label class="block">
                      <span class="text-xs text-slate-500 font-medium">Phone</span>
                      <input x-model="editForm.phone" class="input-field mt-1">
                    </label>
                    <label class="block">
                      <span class="text-xs text-slate-500 font-medium">District</span>
                      <input x-model="editForm.district" class="input-field mt-1">
                    </label>
                    <label class="block">
                      <span class="text-xs text-slate-500 font-medium">State</span>
                      <input x-model="editForm.state" class="input-field mt-1">
                    </label>
                  </div>
                  <div class="flex gap-2">
                    <button @click="saveFarmer()" :disabled="saving"
                            class="btn-primary text-sm px-4 py-2">
                      <span x-text="saving ? 'Saving…' : 'Save changes'"></span>
                    </button>
                    <button @click="deleteFarmer()"
                            class="btn-danger text-sm px-4 py-2">Delete farmer</button>
                  </div>
                  <p x-show="saveMsg" x-text="saveMsg" class="text-green-600 text-sm mt-2"></p>
                </div>
                <!-- tabs: fields / scans / advisories -->
                <div class="flex gap-1 mb-4 border-b border-slate-200">
                  <template x-for="tab in ['Fields','Scans','Advisories']" :key="tab">
                    <button @click="activeTab = tab"
                            class="px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors"
                            :class="activeTab === tab ? 'border-accent text-accent' : 'border-transparent text-slate-500 hover:text-slate-700'">
                      <span x-text="tab"></span>
                    </button>
                  </template>
                </div>
                <div x-show="activeTab === 'Fields'">
                  <!-- fields table rendered via fieldsTableHtml computed -->
                  <div class="overflow-x-auto bg-white rounded-xl border border-slate-100 shadow-sm">
                    <table class="w-full text-sm">
                      <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
                        <th class="px-4 py-3">Name</th><th class="px-4 py-3">Crop</th>
                        <th class="px-4 py-3">Soil</th><th class="px-4 py-3">Area</th>
                        <th class="px-4 py-3">Sown</th><th class="px-4 py-3"></th>
                      </tr></thead>
                      <tbody>
                        <template x-for="fl in farmerFields" :key="fl.id">
                          <tr class="border-b border-slate-50 last:border-0">
                            <td class="px-4 py-3 font-medium" x-text="fl.name"></td>
                            <td class="px-4 py-3 text-slate-600" x-text="fl.current_crop || '—'"></td>
                            <td class="px-4 py-3 text-slate-500 text-xs" x-text="fl.soil_type || '—'"></td>
                            <td class="px-4 py-3 text-slate-500" x-text="fl.area_ha ? fl.area_ha + ' ha' : '—'"></td>
                            <td class="px-4 py-3 text-slate-500" x-text="fl.sown_on || '—'"></td>
                            <td class="px-4 py-3">
                              <button @click="deleteField(fl.id, fl.name)"
                                      class="text-red-500 hover:text-red-700 text-xs font-medium">Delete</button>
                            </td>
                          </tr>
                        </template>
                        <tr x-show="!farmerFields.length">
                          <td colspan="6" class="px-4 py-6 text-slate-400 text-sm text-center">No fields.</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <div x-show="activeTab === 'Scans'" class="overflow-x-auto bg-white rounded-xl border border-slate-100 shadow-sm">
                  <table class="w-full text-sm">
                    <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
                      <th class="px-4 py-3">When</th><th class="px-4 py-3">Field</th>
                      <th class="px-4 py-3">Disease</th><th class="px-4 py-3">Risk</th>
                      <th class="px-4 py-3">Conf.</th><th class="px-4 py-3">Source</th>
                    </tr></thead>
                    <tbody>
                      <template x-for="s in farmerScans" :key="s.id">
                        <tr class="border-b border-slate-50 last:border-0">
                          <td class="px-4 py-3 text-slate-500 text-xs whitespace-nowrap" x-text="fmtDt(s.created_at)"></td>
                          <td class="px-4 py-3" x-text="s.field_name"></td>
                          <td class="px-4 py-3" x-text="s.disease"></td>
                          <td class="px-4 py-3"><span class="risk-badge" :class="'risk-' + s.risk_level" x-text="s.risk_level"></span></td>
                          <td class="px-4 py-3 text-slate-500" x-text="s.confidence != null ? (+s.confidence).toFixed(2) : '—'"></td>
                          <td class="px-4 py-3 text-xs text-slate-500" x-text="s.source"></td>
                        </tr>
                      </template>
                      <tr x-show="!farmerScans.length">
                        <td colspan="6" class="px-4 py-6 text-slate-400 text-sm text-center">No scans yet.</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div x-show="activeTab === 'Advisories'" class="overflow-x-auto bg-white rounded-xl border border-slate-100 shadow-sm">
                  <table class="w-full text-sm">
                    <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
                      <th class="px-4 py-3">When</th><th class="px-4 py-3">Field</th>
                      <th class="px-4 py-3">Title</th><th class="px-4 py-3">Severity</th>
                    </tr></thead>
                    <tbody>
                      <template x-for="a in farmerAdvisories" :key="a.id">
                        <tr class="border-b border-slate-50 last:border-0">
                          <td class="px-4 py-3 text-slate-500 text-xs whitespace-nowrap" x-text="fmtDt(a.created_at)"></td>
                          <td class="px-4 py-3" x-text="a.field_name"></td>
                          <td class="px-4 py-3 max-w-xs truncate" x-text="a.title"></td>
                          <td class="px-4 py-3"><span class="risk-badge" :class="'risk-' + a.severity" x-text="a.severity"></span></td>
                        </tr>
                      </template>
                      <tr x-show="!farmerAdvisories.length">
                        <td colspan="4" class="px-4 py-6 text-slate-400 text-sm text-center">No advisories yet.</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>
          </div>
        </template>

        <template x-if="!detailId">
          <div>
            <div class="flex items-center justify-between mb-6">
              <h1 class="text-xl font-bold text-slate-800">Farmers</h1>
              <span class="text-sm text-slate-500" x-text="filteredFarmers.length + ' of ' + farmers.length"></span>
            </div>
            <div class="flex gap-3 mb-4">
              <input x-model="q" type="search" placeholder="Search name, phone, district…"
                     class="input-field flex-1 max-w-sm">
              <select x-model="langFilter" class="input-field w-40">
                <option value="">All languages</option>
                <option value="en">English</option>
                <option value="kn">Kannada</option>
                <option value="te">Telugu</option>
                <option value="hi">Hindi</option>
              </select>
            </div>
            <div class="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
              <table class="w-full text-sm">
                <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
                  <th class="px-4 py-3">Name</th><th class="px-4 py-3">Phone</th>
                  <th class="px-4 py-3">District</th><th class="px-4 py-3">Language</th>
                  <th class="px-4 py-3">Fields</th><th class="px-4 py-3">Joined</th>
                  <th class="px-4 py-3"></th>
                </tr></thead>
                <tbody>
                  <template x-for="f in filteredFarmers" :key="f.id">
                    <tr class="border-b border-slate-50 last:border-0 hover:bg-slate-50 cursor-pointer"
                        @click="openDetail(f.id)">
                      <td class="px-4 py-3 font-medium text-accent" x-text="f.name"></td>
                      <td class="px-4 py-3 text-slate-500" x-text="f.phone || '—'"></td>
                      <td class="px-4 py-3 text-slate-500" x-text="f.district || '—'"></td>
                      <td class="px-4 py-3 text-slate-500" x-text="langName(f.preferred_language)"></td>
                      <td class="px-4 py-3 text-slate-500" x-text="f.field_count"></td>
                      <td class="px-4 py-3 text-slate-400 text-xs" x-text="(f.created_at || '').slice(0,10)"></td>
                      <td class="px-4 py-3" @click.stop>
                        <button @click="openEdit(f)"
                                class="text-slate-400 hover:text-accent mr-2 text-xs font-medium">Edit</button>
                        <button @click="deleteFarmer(f.id, f.name)"
                                class="text-red-400 hover:text-red-600 text-xs font-medium">Delete</button>
                      </td>
                    </tr>
                  </template>
                  <tr x-show="!filteredFarmers.length">
                    <td colspan="7" class="px-4 py-8 text-slate-400 text-sm text-center">No farmers match.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>

      <div x-show="view === 'fields'" x-data="fieldsPage()" x-init="load()" class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h1 class="text-xl font-bold text-slate-800">Fields</h1>
          <span class="text-sm text-slate-500" x-text="filteredFields.length + ' of ' + fields.length"></span>
        </div>
        <div class="flex gap-3 mb-4">
          <input x-model="q" type="search" placeholder="Search name, crop, farmer…"
                 class="input-field flex-1 max-w-sm">
        </div>
        <div class="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <table class="w-full text-sm">
            <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
              <th class="px-4 py-3">Name</th><th class="px-4 py-3">Farmer</th>
              <th class="px-4 py-3">Crop</th><th class="px-4 py-3">Soil</th>
              <th class="px-4 py-3">Area</th><th class="px-4 py-3">Location</th>
              <th class="px-4 py-3"></th>
            </tr></thead>
            <tbody>
              <template x-for="fl in filteredFields" :key="fl.id">
                <tr class="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                  <td class="px-4 py-3 font-medium" x-text="fl.name"></td>
                  <td class="px-4 py-3 text-slate-500" x-text="fl.farmer_name || '—'"></td>
                  <td class="px-4 py-3 text-slate-500" x-text="fl.current_crop || '—'"></td>
                  <td class="px-4 py-3 text-slate-400 text-xs" x-text="fl.soil_type || '—'"></td>
                  <td class="px-4 py-3 text-slate-500" x-text="fl.area_ha ? fl.area_ha + ' ha' : '—'"></td>
                  <td class="px-4 py-3 text-slate-400 text-xs"
                      x-text="fl.latitude != null ? fl.latitude.toFixed(3) + ', ' + fl.longitude.toFixed(3) : '—'"></td>
                  <td class="px-4 py-3" >
                    <button @click="openEdit(fl)"
                            class="text-slate-400 hover:text-accent mr-2 text-xs font-medium">Edit</button>
                    <button @click="deleteField(fl.id, fl.name)"
                            class="text-red-400 hover:text-red-600 text-xs font-medium">Delete</button>
                  </td>
                </tr>
              </template>
              <tr x-show="!filteredFields.length">
                <td colspan="7" class="px-4 py-8 text-slate-400 text-sm text-center">No fields match.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div x-show="view === 'bugs'" x-data="bugReportsPage()" x-init="load()" class="p-6">
        <div class="flex items-center gap-3 mb-6">
          <h1 class="text-xl font-bold text-slate-800">Bug Reports</h1>
          <span id="bug-live-badge" class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">connecting…</span>
        </div>
        <div class="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <table class="w-full text-sm">
            <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
              <th class="px-4 py-3">When</th><th class="px-4 py-3">Category</th>
              <th class="px-4 py-3">Message</th><th class="px-4 py-3">App ver.</th>
              <th class="px-4 py-3">Status</th><th class="px-4 py-3"></th>
            </tr></thead>
            <tbody>
              <template x-for="r in bugReports" :key="r.id">
                <tr class="border-b border-slate-50 last:border-0">
                  <td class="px-4 py-3 text-slate-400 text-xs whitespace-nowrap" x-text="fmtDt(r.created_at)"></td>
                  <td class="px-4 py-3 text-slate-600 text-xs" x-text="r.category || '—'"></td>
                  <td class="px-4 py-3 max-w-xs truncate text-slate-700" x-text="r.message || '—'"></td>
                  <td class="px-4 py-3 text-slate-400 text-xs" x-text="r.app_version || '—'"></td>
                  <td class="px-4 py-3">
                    <select x-model="r.status" @change="patchStatus(r)"
                            class="text-xs border border-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-accent"
                            :class="statusClass(r.status)">
                      <option value="open">open</option>
                      <option value="triaged">triaged</option>
                      <option value="in_progress">in_progress</option>
                      <option value="resolved">resolved</option>
                    </select>
                  </td>
                  <td class="px-4 py-3">
                    <button @click="deleteReport(r.id)"
                            class="text-red-400 hover:text-red-600 text-xs font-medium">Delete</button>
                  </td>
                </tr>
              </template>
              <tr x-show="!bugReports.length">
                <td colspan="6" class="px-4 py-8 text-slate-400 text-sm text-center">No bug reports yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div x-show="view === 'audit'" x-data="auditLogPage()" x-init="load()" class="p-6">
        <h1 class="text-xl font-bold text-slate-800 mb-6">Audit Log</h1>
        <template x-if="loading"><div class="text-slate-400 text-sm">Loading…</div></template>
        <template x-if="!loading">
          <div class="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
            <table class="w-full text-sm">
              <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
                <th class="px-4 py-3">When</th><th class="px-4 py-3">Action</th>
                <th class="px-4 py-3">Target</th><th class="px-4 py-3">Before / After</th>
              </tr></thead>
              <tbody>
                <template x-for="e in entries" :key="e.id">
                  <tr class="border-b border-slate-50 last:border-0 align-top">
                    <td class="px-4 py-3 text-slate-400 text-xs whitespace-nowrap" x-text="fmtDt(e.created_at)"></td>
                    <td class="px-4 py-3">
                      <span class="text-xs font-medium px-2 py-0.5 rounded-full"
                            :class="e.action === 'delete' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'"
                            x-text="e.action"></span>
                    </td>
                    <td class="px-4 py-3 text-slate-600 text-xs" x-text="e.target_type + ':' + e.target_id.slice(0,8) + '…'"></td>
                    <td class="px-4 py-3">
                      <button @click="e._open = !e._open"
                              class="text-xs text-slate-400 hover:text-accent">
                        <span x-text="e._open ? '▾ hide' : '▸ show'"></span>
                      </button>
                      <div x-show="e._open" class="mt-2 space-y-1">
                        <div x-show="e.before_json" class="text-xs text-slate-500 font-medium">Before:</div>
                        <pre x-show="e.before_json" x-text="prettyJson(e.before_json)" class="json-pre"></pre>
                        <div x-show="e.after_json" class="text-xs text-slate-500 font-medium mt-1">After:</div>
                        <pre x-show="e.after_json" x-text="prettyJson(e.after_json)" class="json-pre"></pre>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr x-show="!entries.length">
                  <td colspan="4" class="px-4 py-8 text-slate-400 text-sm text-center">No audit entries yet.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <div x-show="view === 'otps'" x-data="otpsPage()" x-init="startPolling()" class="p-6"
           @view-changed.window="if($event.detail !== 'otps') stopPolling()">
        <h1 class="text-xl font-bold text-slate-800 mb-2">Pending OTPs</h1>
        <p class="text-sm text-slate-500 mb-5">Dev/test mode only. Refreshes every 5 s while this page is open.</p>
        <div class="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <table class="w-full text-sm">
            <thead><tr class="text-left text-xs text-slate-500 border-b border-slate-200 bg-slate-50">
              <th class="px-4 py-3">Phone</th><th class="px-4 py-3">Code</th>
              <th class="px-4 py-3">Issued</th><th class="px-4 py-3">Expires</th>
            </tr></thead>
            <tbody>
              <template x-for="o in otps" :key="o.phone + o.code">
                <tr class="border-b border-slate-50 last:border-0">
                  <td class="px-4 py-3 text-slate-600" x-text="o.phone"></td>
                  <td class="px-4 py-3"><code class="bg-slate-100 rounded px-2 py-0.5 text-xs font-mono" x-text="o.code"></code></td>
                  <td class="px-4 py-3 text-slate-400 text-xs" x-text="fmtDt(o.issued_at)"></td>
                  <td class="px-4 py-3 text-slate-400 text-xs" x-text="fmtDt(o.expires_at)"></td>
                </tr>
              </template>
              <tr x-show="!otps.length">
                <td colspan="4" class="px-4 py-8 text-slate-400 text-sm text-center">No pending OTPs.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </main>
  </div>

  <script src="admin.js"></script>
</body>
</html>
```

- [ ] **Step 2: Rewrite `style.css`**

Replace the entire file with:

```css
/* Custom overrides — Tailwind handles everything else */
[x-cloak] { display: none !important; }

.chart-canvas { max-height: 200px; }

.input-field {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.375rem 0.625rem;
  font-size: 0.875rem;
  outline: none;
}
.input-field:focus { ring: 2px solid #22c55e; }

.btn-primary {
  background: #22c55e; color: white; font-weight: 600;
  border-radius: 0.5rem; cursor: pointer; transition: opacity .15s;
}
.btn-primary:hover { opacity: .88; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

.btn-danger {
  background: #dc2626; color: white; font-weight: 600;
  border-radius: 0.5rem; cursor: pointer; transition: opacity .15s;
}
.btn-danger:hover { opacity: .88; }

/* Risk / severity badges */
.risk-badge {
  display: inline-block;
  font-size: 0.7rem; font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
}
.risk-low    { background: #dcfce7; color: #166534; }
.risk-moderate { background: #fef9c3; color: #854d0e; }
.risk-high   { background: #ffedd5; color: #c2410c; }
.risk-severe { background: #fee2e2; color: #991b1b; }

/* Audit log JSON block */
.json-pre {
  font-size: 0.7rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  padding: 0.5rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
}
```

- [ ] **Step 3: Smoke-test login card renders**

Open `web/admin/index.html` in browser (or via dev server). Should see the dark centered login card with green focus ring. No JS errors in console.

- [ ] **Step 4: Commit**

```bash
git add web/admin/index.html web/admin/style.css
git commit -m "feat(admin): new HTML shell + Tailwind/Alpine CDN, polished login card"
```

---

## Task 2: Core Alpine App Shell (`adminApp`)

**Files:**
- Create: `web/admin/admin.js` (full rewrite — start fresh)

**Goal:** Register the `adminApp()` Alpine data object that drives all routing, auth state, toast, confirm modal, and edit drawer.

**Interfaces:**
- Produces: `adminApp()` → `{ authed, view, unreadBugs, otpDevMode, navItems, loginEmail, loginPassword, loginBusy, loginError, toast, confirm, drawer, init(), login(), logout(), navigate(view), showToast(msg, type), showConfirm(expected, onConfirm), openDrawer(title, bodyHtml, saveFn) }`
- Produces: `api(path, opts?)` → `Promise<any>` (shared fetch helper)
- Produces: `apiJSON(path, method, body)` → `Promise<any>`
- Produces: `langName(code)` → `string`
- Produces: `fmtDt(iso)` → `string`

- [ ] **Step 1: Write `admin.js` with `adminApp` and shared helpers**

```javascript
// Shared helpers (module-level, used by all Alpine components)
const LANGS = { en: 'English', kn: 'Kannada', te: 'Telugu', hi: 'Hindi' };
function langName(c) { return LANGS[c] || c || 'unknown'; }
function fmtDt(iso) { return iso ? iso.replace('T', ' ').slice(0, 16) : '—'; }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function api(path, opts = {}) {
  return fetch(path, { credentials: 'same-origin', ...opts }).then(r => {
    if (r.status === 401) { const e = new Error('unauthorized'); e.code = 401; throw e; }
    if (!r.ok) return r.json().catch(() => ({})).then(b => {
      throw new Error((b.error && b.error.message) || `${path} → ${r.status}`);
    });
    if (r.status === 204) return null;
    return r.json();
  });
}
function apiJSON(path, method, body) {
  return api(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

// Chart.js registry (destroyed and recreated on navigation)
const _charts = {};
function destroyChart(id) { if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; } }
function makeBarChart(id, labels, values, color = '#22c55e') {
  destroyChart(id);
  const ctx = document.getElementById(id);
  if (!ctx) return;
  _charts[id] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: color + 'cc', borderRadius: 4 }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { stepSize: 1 } }, y: { ticks: { font: { size: 11 } } } },
    }
  });
}

// ---- Main app shell ----
function adminApp() {
  return {
    authed: false,
    view: 'overview',
    unreadBugs: 0,
    otpDevMode: false,
    loginEmail: '',
    loginPassword: '',
    loginBusy: false,
    loginError: '',
    toast: { show: false, msg: '', type: 'info', _timer: null },
    confirm: { show: false, expected: '', typed: '', onConfirm: null },
    drawer: { show: false, title: '', bodyHtml: '', save: null, saving: false, error: '' },

    navItems: [
      { view: 'overview', hash: '',        icon: '📊', label: 'Overview' },
      { view: 'farmers',  hash: 'farmers', icon: '👩‍🌾', label: 'Farmers' },
      { view: 'fields',   hash: 'fields',  icon: '🌾', label: 'Fields' },
      { view: 'bugs',     hash: 'bugs',    icon: '🐛', label: 'Bug Reports' },
      { view: 'audit',    hash: 'audit',   icon: '📋', label: 'Audit Log' },
      { view: 'otps',     hash: 'otps',    icon: '🔑', label: 'OTPs (dev)' },
    ],

    init() {
      // Try existing session
      api('/v2/admin/overview').then(d => {
        this.otpDevMode = d.otp_dev_mode === true;
        this.authed = true;
        this._routeFromHash();
      }).catch(e => {
        if (e.code !== 401) this.loginError = 'Backend unreachable.';
      });
      window.addEventListener('hashchange', () => this._routeFromHash());
      this.$watch('view', v => window.dispatchEvent(new CustomEvent('view-changed', { detail: v })));
    },

    _routeFromHash() {
      const h = location.hash.replace(/^#\/?/, '') || '';
      const map = { '': 'overview', farmers: 'farmers', fields: 'fields', bugs: 'bugs', audit: 'audit', otps: 'otps' };
      this.view = map[h.split('/')[0]] || 'overview';
      if (this.view === 'bugs') this.unreadBugs = 0;
    },

    navigate(v) {
      this.view = v;
      if (v === 'bugs') this.unreadBugs = 0;
    },

    login() {
      this.loginBusy = true;
      this.loginError = '';
      const body = new URLSearchParams({ email: this.loginEmail, password: this.loginPassword });
      fetch('/admin/login', { method: 'POST', body, credentials: 'same-origin' })
        .then(r => {
          const p = new URL(r.url).pathname.replace(/\/$/, '');
          if (p !== '/admin') return r.text().then(t => {
            const m = /class="flash flash-error"[^>]*>([^<]+)</.exec(t);
            throw new Error(m ? m[1].trim() : 'Invalid email or password');
          });
          return api('/v2/admin/overview').then(d => { this.otpDevMode = d.otp_dev_mode === true; });
        })
        .then(() => { this.authed = true; this.loginEmail = ''; this.loginPassword = ''; this.view = 'overview'; })
        .catch(e => { this.loginError = e.message || 'Sign in failed'; })
        .finally(() => { this.loginBusy = false; });
    },

    logout() {
      fetch('/admin/logout', { method: 'POST', credentials: 'same-origin' })
        .finally(() => { this.authed = false; this.view = 'overview'; this.unreadBugs = 0; });
    },

    showToast(msg, type = 'info') {
      clearTimeout(this.toast._timer);
      this.toast = { show: true, msg, type, _timer: setTimeout(() => { this.toast.show = false; }, 4000) };
    },

    showConfirm(expected, onConfirm) {
      this.confirm = { show: true, expected, typed: '', onConfirm: () => {
        onConfirm().then(() => { this.confirm.show = false; })
          .catch(e => this.showToast(e.message || 'Delete failed', 'error'));
      }};
      this.$nextTick(() => { const el = this.$refs.confirmInput; if (el) el.focus(); });
    },

    openDrawer(title, bodyHtml, saveFn) {
      this.drawer = { show: true, title, bodyHtml, save: saveFn, saving: false, error: '' };
    },
  };
}
```

- [ ] **Step 2: Register with Alpine**

At the bottom of `admin.js`, add:

```javascript
document.addEventListener('alpine:init', () => {
  Alpine.data('adminApp', adminApp);
});
```

- [ ] **Step 3: Smoke-test in browser**

Login should work: sign in with admin credentials → sidebar appears → clicking nav items changes `view` → toast fires on any `showToast` call (test in console: `Alpine.$data(document.body).showToast('test')`).

- [ ] **Step 4: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): adminApp Alpine shell — routing, login, toast, confirm, drawer"
```

---

## Task 3: Overview Page (`overviewPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `makeBarChart()`, `fmtDt()`, `langName()` from Task 2
- Produces: `overviewPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `overviewPage` to `admin.js`**

```javascript
function overviewPage() {
  return {
    loading: true,
    statCards: [],
    recentActivity: [],
    _farmers: [],
    _fields: [],

    load() {
      Promise.all([
        api('/v2/admin/overview'),
        api('/v2/admin/farmers'),
        api('/v2/admin/fields'),
        api('/v2/admin/scans'),
        api('/v2/admin/advisories'),
      ]).then(([ov, fa, fi, sc, ad]) => {
        this._farmers = fa.items;
        this._fields = fi.items;
        const fb = ov.feedback || {};
        const withFields = fa.items.filter(f => f.field_count > 0).length;
        this.statCards = [
          { label: 'Total Farmers', value: fa.items.length, note: `${withFields} with fields` },
          { label: 'Total Fields', value: fi.items.length, note: '' },
          { label: 'Disease Scans', value: sc.items.length, note: 'image uploads' },
          { label: 'Advisories', value: ad.items.length, note: '' },
          { label: 'Open Bugs', value: ov.open_bug_count ?? '—', note: '' },
          { label: 'Avg Feedback', value: fb.mean_rating != null ? (+fb.mean_rating).toFixed(1) + ' ★' : '—',
            note: fb.helpful_rate != null ? Math.round(fb.helpful_rate * 100) + '% helpful' : '' },
        ];
        // recent activity: merge scans + advisories, sort desc, top 20
        const rows = [
          ...sc.items.map(s => ({ type: 'Scan', created_at: s.created_at, field_name: s.field_name, detail: s.disease })),
          ...ad.items.map(a => ({ type: 'Advisory', created_at: a.created_at, field_name: a.field_name, detail: a.severity })),
        ].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')).slice(0, 20);
        this.recentActivity = rows.map(r => ({ ...r, when: fmtDt(r.created_at) }));
        this.loading = false;
        this.$nextTick(() => this._drawCharts());
      }).catch(e => { this.loading = false; console.error('overview load', e); });
    },

    _drawCharts() {
      // Crop distribution
      const cropCounts = {};
      this._fields.forEach(f => { const k = f.current_crop || 'unknown'; cropCounts[k] = (cropCounts[k] || 0) + 1; });
      const cropSorted = Object.entries(cropCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
      makeBarChart('cropChart', cropSorted.map(r => r[0]), cropSorted.map(r => r[1]));

      // Language distribution
      const langCounts = {};
      this._farmers.forEach(f => { const k = f.preferred_language || 'unknown'; langCounts[k] = (langCounts[k] || 0) + 1; });
      const langSorted = Object.entries(langCounts).sort((a, b) => b[1] - a[1]);
      makeBarChart('langChart', langSorted.map(r => langName(r[0])), langSorted.map(r => r[1]), '#3b82f6');
    },
  };
}
```

Add to the `alpine:init` block:
```javascript
Alpine.data('overviewPage', overviewPage);
```

- [ ] **Step 2: Verify in browser**

Navigate to Overview: 6 stat cards visible, two Chart.js bar charts render, recent activity table populates. Navigate away and back — charts redraw without "Canvas already in use" error.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): overviewPage — stat cards, Chart.js crop/language bars, activity feed"
```

---

## Task 4: Farmers Page (`farmersPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `apiJSON()`, `langName()` from Task 2
- Consumes: `adminApp.showToast`, `adminApp.showConfirm`, `adminApp.openDrawer` — called via `this.$dispatch` custom event pattern
- Produces: `farmersPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `farmersPage` to `admin.js`**

```javascript
function farmersPage() {
  return {
    farmers: [],
    q: '',
    langFilter: '',
    detailId: null,  // null = list, string = farmer detail

    get filteredFarmers() {
      const q = this.q.trim().toLowerCase();
      return this.farmers.filter(f => {
        if (this.langFilter && f.preferred_language !== this.langFilter) return false;
        if (!q) return true;
        return [f.name, f.phone, f.district, f.state].join(' ').toLowerCase().includes(q);
      });
    },

    load() {
      api('/v2/admin/farmers').then(r => { this.farmers = r.items; })
        .catch(e => window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } })));
    },

    openDetail(id) { this.detailId = id; },

    openEdit(f) {
      const html = `
        <div class="space-y-4">
          <label class="block"><span class="text-xs text-slate-500 font-medium">Name</span>
            <input id="de-name" class="input-field mt-1" value="${esc(f.name)}"></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">Phone</span>
            <input id="de-phone" class="input-field mt-1" value="${esc(f.phone || '')}"></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">Language</span>
            <select id="de-lang" class="input-field mt-1">
              ${['en','kn','te','hi'].map(l => `<option value="${l}" ${f.preferred_language===l?'selected':''}>${langName(l)}</option>`).join('')}
            </select></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">District</span>
            <input id="de-district" class="input-field mt-1" value="${esc(f.district || '')}"></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">State</span>
            <input id="de-state" class="input-field mt-1" value="${esc(f.state || '')}"></label>
        </div>`;
      const saveFn = () => {
        const patch = {
          name: document.getElementById('de-name').value,
          phone: document.getElementById('de-phone').value,
          preferred_language: document.getElementById('de-lang').value,
          district: document.getElementById('de-district').value,
          state: document.getElementById('de-state').value,
        };
        return apiJSON(`/v2/admin/farmers/${encodeURIComponent(f.id)}`, 'PATCH', patch)
          .then(updated => {
            this.farmers = this.farmers.map(x => x.id === f.id ? { ...x, ...updated } : x);
            window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: 'Saved.' } }));
          });
      };
      window.dispatchEvent(new CustomEvent('admin-open-drawer', { detail: { title: `Edit: ${f.name}`, html, saveFn } }));
    },

    deleteFarmer(id, name) {
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: () => api(`/v2/admin/farmers/${encodeURIComponent(id)}`, { method: 'DELETE' })
          .then(() => { this.farmers = this.farmers.filter(x => x.id !== id); })
      }}));
    },
  };
}
```

> **Note:** The drawer, toast, and confirm live on the `adminApp` shell. They are triggered via custom window events (`admin-toast`, `admin-confirm`, `admin-open-drawer`) so child Alpine components don't need a direct reference to the parent. Wire these event listeners in `adminApp.init()`:

```javascript
// Add to adminApp.init():
window.addEventListener('admin-toast', e => this.showToast(e.detail.msg, e.detail.type || 'info'));
window.addEventListener('admin-confirm', e => this.showConfirm(e.detail.expected, e.detail.onConfirm));
window.addEventListener('admin-open-drawer', e => {
  this.openDrawer(e.detail.title, e.detail.html, () => {
    this.drawer.saving = true;
    this.drawer.error = '';
    return e.detail.saveFn()
      .then(() => { this.drawer.show = false; })
      .catch(err => { this.drawer.error = err.message; })
      .finally(() => { this.drawer.saving = false; });
  });
});
```

Add to the `alpine:init` block:
```javascript
Alpine.data('farmersPage', farmersPage);
```

- [ ] **Step 2: Verify in browser**

Farmers list: search filters work, clicking row opens detail placeholder, Edit button opens drawer with pre-filled fields, Save patches correctly, Delete triggers confirm modal.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): farmersPage — list, search, edit drawer, delete confirm"
```

---

## Task 5: Farmer Detail Page (`farmerDetailPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `apiJSON()`, `langName()`, `fmtDt()` from Task 2
- Produces: `farmerDetailPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `farmerDetailPage` to `admin.js`**

```javascript
function farmerDetailPage() {
  return {
    loading: true,
    farmer: null,
    farmerFields: [],
    farmerScans: [],
    farmerAdvisories: [],
    activeTab: 'Fields',
    editForm: { name: '', phone: '', district: '', state: '' },
    saving: false,
    saveMsg: '',

    load(id) {
      this.loading = true;
      Promise.all([
        api('/v2/admin/farmers'),
        api('/v2/admin/fields'),
        api('/v2/admin/scans'),
        api('/v2/admin/advisories'),
      ]).then(([fa, fi, sc, ad]) => {
        this.farmer = fa.items.find(f => f.id === id);
        if (!this.farmer) { this.loading = false; return; }
        this.editForm = { name: this.farmer.name, phone: this.farmer.phone || '',
                          district: this.farmer.district || '', state: this.farmer.state || '' };
        this.farmerFields = fi.items.filter(f => f.farmer_id === id);
        this.farmerScans = sc.items.filter(s => s.farmer_id === id);
        this.farmerAdvisories = ad.items.filter(a => a.farmer_id === id);
        this.loading = false;
      }).catch(e => { this.loading = false; console.error(e); });
    },

    saveFarmer() {
      this.saving = true;
      this.saveMsg = '';
      apiJSON(`/v2/admin/farmers/${encodeURIComponent(this.farmer.id)}`, 'PATCH', this.editForm)
        .then(() => { this.saveMsg = 'Saved.'; setTimeout(() => { this.saveMsg = ''; }, 2000); })
        .catch(e => { this.saveMsg = e.message; })
        .finally(() => { this.saving = false; });
    },

    deleteFarmer() {
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: this.farmer.name,
        onConfirm: () => api(`/v2/admin/farmers/${encodeURIComponent(this.farmer.id)}`, { method: 'DELETE' })
          .then(() => window.dispatchEvent(new CustomEvent('nav-farmers-list')))
      }}));
    },

    deleteField(id, name) {
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: () => api(`/v2/admin/fields/${encodeURIComponent(id)}`, { method: 'DELETE' })
          .then(() => { this.farmerFields = this.farmerFields.filter(f => f.id !== id); })
      }}));
    },

    langName, fmtDt,
  };
}
```

Also add a `nav-farmers-list` listener in `adminApp.init()` to clear `detailId` on the farmersPage:
```javascript
// In adminApp.init(), add:
window.addEventListener('nav-farmers-list', () => {
  // farmersPage is the nearest Alpine component on the farmers section —
  // dispatch via the hash instead (simpler):
  location.hash = '#/farmers';
  this.view = 'farmers';
  // farmersPage itself clears detailId on re-init if we use x-if rather than x-show;
  // since we used x-if for the two sub-sections, detailId resets when farmers view reloads.
});
```

> **Implementation note:** In `index.html`, the farmers section uses `<template x-if="detailId">` and `<template x-if="!detailId">` so only one sub-section exists in the DOM at a time. Navigating away and back resets `detailId` to `null` (its initial value on `farmersPage` init).

Add to the `alpine:init` block:
```javascript
Alpine.data('farmerDetailPage', farmerDetailPage);
```

- [ ] **Step 2: Verify**

Click a farmer row → detail page loads with tabs → Scans / Advisories tabs work → Edit form saves → Delete triggers confirm → breadcrumb goes back to list.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): farmerDetailPage — edit form, tabs (Fields/Scans/Advisories), delete"
```

---

## Task 6: Fields Page (`fieldsPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `apiJSON()` from Task 2
- Produces: `fieldsPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `fieldsPage` to `admin.js`**

```javascript
const SOIL_TYPES = ['alluvial','black','desert','laterite','mountain','peaty','red','saline','unknown'];

function fieldsPage() {
  return {
    fields: [],
    q: '',

    get filteredFields() {
      const q = this.q.trim().toLowerCase();
      if (!q) return this.fields;
      return this.fields.filter(f =>
        [f.name, f.current_crop, f.farmer_name, f.soil_type].join(' ').toLowerCase().includes(q)
      );
    },

    load() {
      Promise.all([api('/v2/admin/fields'), api('/v2/admin/farmers')]).then(([fi, fa]) => {
        const farmerMap = {};
        fa.items.forEach(f => { farmerMap[f.id] = f.name; });
        this.fields = fi.items.map(f => ({ ...f, farmer_name: farmerMap[f.farmer_id] || '—' }));
      }).catch(e => window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } })));
    },

    openEdit(fl) {
      const soilOptions = SOIL_TYPES.map(s =>
        `<option value="${s}" ${fl.soil_type === s ? 'selected' : ''}>${s}</option>`).join('');
      const html = `
        <div class="space-y-4">
          <label class="block"><span class="text-xs text-slate-500 font-medium">Name</span>
            <input id="de-name" class="input-field mt-1" value="${esc(fl.name)}"></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block"><span class="text-xs text-slate-500 font-medium">Latitude</span>
              <input id="de-lat" type="number" step="0.0001" class="input-field mt-1" value="${fl.latitude ?? ''}"></label>
            <label class="block"><span class="text-xs text-slate-500 font-medium">Longitude</span>
              <input id="de-lng" type="number" step="0.0001" class="input-field mt-1" value="${fl.longitude ?? ''}"></label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="block"><span class="text-xs text-slate-500 font-medium">Area (ha)</span>
              <input id="de-area" type="number" step="0.01" class="input-field mt-1" value="${fl.area_ha ?? ''}"></label>
            <label class="block"><span class="text-xs text-slate-500 font-medium">Elevation (m)</span>
              <input id="de-elev" type="number" class="input-field mt-1" value="${fl.elevation_m ?? ''}"></label>
          </div>
          <label class="block"><span class="text-xs text-slate-500 font-medium">Soil type</span>
            <select id="de-soil" class="input-field mt-1">${soilOptions}</select></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">Current crop</span>
            <input id="de-crop" class="input-field mt-1" value="${esc(fl.current_crop || '')}"></label>
          <label class="block"><span class="text-xs text-slate-500 font-medium">Sown on</span>
            <input id="de-sown" type="date" class="input-field mt-1" value="${esc(fl.sown_on || '')}"></label>
        </div>`;
      const saveFn = () => {
        const patch = {
          name: document.getElementById('de-name').value,
          latitude: parseFloat(document.getElementById('de-lat').value) || null,
          longitude: parseFloat(document.getElementById('de-lng').value) || null,
          area_ha: parseFloat(document.getElementById('de-area').value) || null,
          elevation_m: document.getElementById('de-elev').value ? +document.getElementById('de-elev').value : null,
          soil_type: document.getElementById('de-soil').value,
          current_crop: document.getElementById('de-crop').value,
          sown_on: document.getElementById('de-sown').value || null,
        };
        return apiJSON(`/v2/admin/fields/${encodeURIComponent(fl.id)}`, 'PATCH', patch)
          .then(updated => {
            this.fields = this.fields.map(f => f.id === fl.id ? { ...f, ...updated } : f);
            window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: 'Saved.' } }));
          });
      };
      window.dispatchEvent(new CustomEvent('admin-open-drawer', { detail: { title: `Edit field: ${fl.name}`, html, saveFn } }));
    },

    deleteField(id, name) {
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: name,
        onConfirm: () => api(`/v2/admin/fields/${encodeURIComponent(id)}`, { method: 'DELETE' })
          .then(() => { this.fields = this.fields.filter(f => f.id !== id); })
      }}));
    },
  };
}
```

Add to `alpine:init`:
```javascript
Alpine.data('fieldsPage', fieldsPage);
```

- [ ] **Step 2: Verify**

Fields list loads, search filters, Edit drawer opens with all 8 fields pre-filled, Save patches correctly, Delete confirm works.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): fieldsPage — list, search, full edit drawer (8 fields), delete"
```

---

## Task 7: Bug Reports Page + SSE Live Badge (`bugReportsPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `apiJSON()`, `fmtDt()` from Task 2
- Produces: `bugReportsPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `bugReportsPage` to `admin.js`**

```javascript
function bugReportsPage() {
  let _stream = null;

  return {
    bugReports: [],

    statusClass(s) {
      return {
        open:        'bg-red-50 text-red-700',
        triaged:     'bg-amber-50 text-amber-700',
        in_progress: 'bg-blue-50 text-blue-700',
        resolved:    'bg-green-50 text-green-700',
      }[s] || '';
    },

    fmtDt,

    load() {
      api('/v2/admin/bug-reports').then(r => {
        this.bugReports = r.items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        this._startStream();
      }).catch(e => window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } })));
    },

    _startStream() {
      if (_stream) return;
      _stream = new EventSource('/v2/admin/stream/bug-reports');
      const badge = document.getElementById('bug-live-badge');
      _stream.onopen = () => {
        if (badge) { badge.textContent = 'live'; badge.className = 'text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700'; }
      };
      _stream.onmessage = ev => {
        const report = JSON.parse(ev.data);
        this.bugReports = [report, ...this.bugReports.filter(r => r.id !== report.id)];
        // Increment unread badge on shell
        window.dispatchEvent(new CustomEvent('admin-new-bug'));
      };
      _stream.onerror = () => {
        if (badge) { badge.textContent = 'reconnecting…'; badge.className = 'text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500'; }
      };
    },

    patchStatus(r) {
      apiJSON(`/v2/admin/bug-reports/${encodeURIComponent(r.id)}`, 'PATCH', { status: r.status })
        .catch(e => window.dispatchEvent(new CustomEvent('admin-toast', { detail: { msg: e.message, type: 'error' } })));
    },

    deleteReport(id) {
      window.dispatchEvent(new CustomEvent('admin-confirm', { detail: {
        expected: id.slice(0, 8),
        onConfirm: () => api(`/v2/admin/bug-reports/${encodeURIComponent(id)}`, { method: 'DELETE' })
          .then(() => { this.bugReports = this.bugReports.filter(r => r.id !== id); })
      }}));
    },
  };
}
```

Add to `adminApp.init()`:
```javascript
window.addEventListener('admin-new-bug', () => {
  if (this.view !== 'bugs') this.unreadBugs++;
});
```

Add to `alpine:init`:
```javascript
Alpine.data('bugReportsPage', bugReportsPage);
```

- [ ] **Step 2: Verify SSE badge** (Review Focus item)

Open the page and wait. Badge shows "connecting…" then "live" when SSE connects. Navigate to another tab — badge on sidebar nav shows count if new reports arrive. Navigate back to Bug Reports — count resets to 0. On Render cold-start (simulate by disabling network briefly), badge shows "reconnecting…" without error.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): bugReportsPage — table, SSE live badge, status patch, delete"
```

---

## Task 8: Audit Log Page (`auditLogPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `fmtDt()` from Task 2
- Produces: `auditLogPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `auditLogPage` to `admin.js`**

```javascript
function auditLogPage() {
  return {
    loading: true,
    entries: [],
    fmtDt,

    prettyJson(jsonStr) {
      if (!jsonStr) return '';
      try { return JSON.stringify(JSON.parse(jsonStr), null, 2); }
      catch { return jsonStr; }
    },

    load() {
      api('/v2/admin/audit-log').then(r => {
        this.entries = r.items.map(e => ({ ...e, _open: false }));
        this.loading = false;
      }).catch(e => { this.loading = false; console.error(e); });
    },
  };
}
```

Add to `alpine:init`:
```javascript
Alpine.data('auditLogPage', auditLogPage);
```

- [ ] **Step 2: Verify**

Audit Log shows entries. Clicking ▸ expands the before/after JSON in a scrollable `<pre>` block. Clicking again collapses it.

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): auditLogPage — entries table, collapsible JSON diff"
```

---

## Task 9: OTPs Page (`otpsPage`)

**Files:**
- Modify: `web/admin/admin.js` (append)

**Interfaces:**
- Consumes: `api()`, `fmtDt()` from Task 2
- Produces: `otpsPage()` registered with `Alpine.data`

- [ ] **Step 1: Append `otpsPage` to `admin.js`**

```javascript
function otpsPage() {
  let _timer = null;

  return {
    otps: [],
    fmtDt,

    startPolling() {
      this._fetch();
      _timer = setInterval(() => this._fetch(), 5000);
    },

    stopPolling() {
      if (_timer) { clearInterval(_timer); _timer = null; }
    },

    _fetch() {
      api('/v2/admin/otps').then(r => { this.otps = r.items; })
        .catch(() => {}); // silent — OTPs are best-effort
    },
  };
}
```

Add to `alpine:init`:
```javascript
Alpine.data('otpsPage', otpsPage);
```

> **Review Focus (OTP polling cleanup):** The `otpsPage` section uses `x-init="startPolling()"` and listens to `@view-changed.window` to call `stopPolling()`. This is already wired in the HTML from Task 1. Verify the interval is cleared when navigating away by checking `clearInterval` fires in the console.

- [ ] **Step 2: Verify**

OTPs tab only appears when `otpDevMode === true`. Table auto-refreshes every 5 s while open. Navigating away stops the interval (verify: no further fetch requests to `/v2/admin/otps` after leaving the tab).

- [ ] **Step 3: Commit**

```bash
git add web/admin/admin.js
git commit -m "feat(admin): otpsPage — polled table, auto-stop on nav away"
```

---

## Task 10: Full Smoke Test + Cleanup

**Files:**
- Review: `web/admin/admin.js` (ensure all `alpine:init` registrations are present)
- Review: `web/admin/index.html` (ensure no stale IDs from old code)

- [ ] **Step 1: Verify all Alpine.data registrations**

At the bottom of `admin.js`, the `alpine:init` listener must register all components:

```javascript
document.addEventListener('alpine:init', () => {
  Alpine.data('adminApp',        adminApp);
  Alpine.data('overviewPage',    overviewPage);
  Alpine.data('farmersPage',     farmersPage);
  Alpine.data('farmerDetailPage',farmerDetailPage);
  Alpine.data('fieldsPage',      fieldsPage);
  Alpine.data('bugReportsPage',  bugReportsPage);
  Alpine.data('auditLogPage',    auditLogPage);
  Alpine.data('otpsPage',        otpsPage);
});
```

- [ ] **Step 2: Full smoke test checklist**

Run against production (Vercel) or local dev server (`node web/admin/dev-server.mjs`):

```
□ Login: wrong password → error banner shown
□ Login: correct credentials → sidebar + overview loads
□ Overview: 6 stat cards, 2 charts, activity feed
□ Chart navigation: Overview → Farmers → Overview: no "Canvas already in use" error
□ Farmers list: search filters correctly, language dropdown filters correctly
□ Farmers edit drawer: opens pre-filled, saves, toast fires
□ Farmers delete: confirm modal, type name, farmer removed from list
□ Farmer detail: breadcrumb, 3 tabs (Fields/Scans/Advisories) all load
□ Farmer detail edit: saves farmer name change
□ Fields list: loads, search filters, edit drawer opens with soil_type select
□ Fields delete: confirm modal uses field name
□ Bug Reports: table loads, SSE badge shows "live"
□ Bug Reports: status dropdown change → PATCH fires
□ Bug Reports: delete triggers confirm with 8-char ID prefix
□ Audit Log: entries load, ▸ toggles JSON expand/collapse
□ OTPs: tab hidden in production, shown when otp_dev_mode=true
□ Sign out → returns to login screen
□ No JS console errors on any page
```

- [ ] **Step 3: Fix any issues found in smoke test**

- [ ] **Step 4: Final commit**

```bash
git add web/admin/admin.js web/admin/index.html web/admin/style.css
git commit -m "feat(admin): Module 54 complete — polished Tailwind/Alpine dashboard"
```

---

## Self-Review Notes

**Spec coverage check:**
- Login page → Task 1 ✅
- Sidebar layout → Task 1 (HTML) + Task 2 (Alpine) ✅
- Overview 6 stat cards + Chart.js → Task 3 ✅
- Farmers list + edit drawer → Task 4 ✅
- Farmer detail tabs → Task 5 ✅
- Fields list + edit drawer → Task 6 ✅
- Bug Reports + SSE → Task 7 ✅
- Audit Log + JSON diff → Task 8 ✅
- OTPs (dev mode only) → Task 9 ✅
- Toast notifications → Task 2 (adminApp) ✅
- Confirm modal → Task 2 (adminApp) ✅
- Edit drawer (shared) → Task 2 (adminApp) ✅

**Review Focus addressed:**
1. Login redirect detection (`/admin` vs `/admin/`) → `pathname.replace(/\/$/, '')` in Task 2 login() ✅
2. SSE reconnect badge → Task 7 `_stream.onerror` handler ✅
3. Chart.js canvas reuse → `destroyChart()` called before `new Chart()` in Task 3 ✅
4. OTP polling cleanup → `@view-changed.window` listener in HTML (Task 1) + `stopPolling()` in Task 9 ✅
5. Confirm modal focus trap → `this.$nextTick(() => el.focus())` in `adminApp.showConfirm` ✅
