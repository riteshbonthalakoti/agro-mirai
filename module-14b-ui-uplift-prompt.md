# MODULE 14b — UI/UX Uplift (Web Frontend)

Continuing AGRO MIRAI in the existing `agro-mirai` repo. Module 14
(Frontend) is done, committed, and functionally correct — 15/15 tests
pass, it calls the real API, real data renders. This module does NOT
touch functionality or the API contract. It exists because the current
UI, while working, is a bare-minimum utilitarian shell (single accent
color, system fonts, 114 lines of CSS, no visual hierarchy, no motion,
no data visualization, no responsive design) — not something you'd want
to demo to VTU evaluators or put in a capstone report as a screenshot.
This module's only job is to make `src/agro_mirai/api/templates/` and
`src/agro_mirai/api/static/` genuinely impressive without breaking
anything underneath.

Read `CLAUDE.md`, `PROGRESS.md`, and the existing
`decisions/0013-frontend-platform-sequencing.md` first. Confirm
`git config user.name`/`user.email`. Same commit discipline as prior
modules — but this one can be more iterative: commit at real visual
milestones (e.g. "design system + tokens", "dashboard redesign",
"field detail redesign", "feedback flow polish", "responsive + motion
pass") rather than one giant commit.

## Hard constraints — do not break these

- Do not change any Flask route signatures, `openapi.yaml`, or how data
  flows from `DecisionEngine`/`DataStore` into the templates. This is a
  presentation-layer change only.
- Every existing test in `tests/api/` (unit + integration) must still
  pass unmodified — they assert on route behavior and response
  presence, not on exact markup, so a good redesign shouldn't need to
  touch them. If a test genuinely breaks because it was asserting on
  specific HTML structure, fix the test to check the right thing, and
  say so explicitly in the handoff — don't loosen a test just to make
  it pass.
- Keep it a server-rendered Flask/Jinja2 app (per ADR 0013's stack
  decision) — this is a visual/CSS/light-JS uplift, not a framework
  migration to React/Vue/etc.
- No new backend dependencies. Frontend-only libraries (fonts, icon
  sets, a CSS framework, a small animation library) are fine as long as
  they're either self-hosted/vendored or loaded from a CDN with a
  documented fallback — check `docs/architecture.md`'s stance on
  external dependencies for a free-tier capstone before pulling in
  anything with a cost or account requirement.

## Tooling — check what's actually available first

Before writing any HTML/CSS by hand, check what design tooling exists
in this environment:
1. Check whether a `stitch` CLI (Google's AI UI-design tool) is
   installed and authenticated (`which stitch`, `stitch --help`, or
   check for existing config). If it's available and working, use it to
   generate/iterate on high-fidelity screen designs for the dashboard,
   field-detail, and feedback screens, then adapt its output into the
   actual Jinja2 templates — don't just paste Stitch's raw scaffold in
   if it assumes a different stack; translate the visual design
   (layout, spacing, type scale, color, iconography) into this app's
   real templates and real data bindings.
2. If `stitch` isn't available or isn't authenticated, don't block on
   it or spend time trying to set it up — proceed with the manual
   design system approach below and note in the handoff that Stitch
   wasn't available.
3. Either way, the deliverable is real, working, tested Jinja2
   templates + CSS in this repo — not a mockup that isn't wired to live
   data.

## Design direction

This is an agriculture advisory product for Indian farmers and
extension workers, viewed on a mix of desktop (evaluators, dashboards)
and mobile (field use). Aim for something that feels credible,
modern, and calm — not a generic SaaS dashboard template, and not
twee/cartoonish "farm" clip-art. Think: confident use of a real type
scale, generous whitespace, one strong accent color plus a considered
neutral palette, actual data visualization for the advisory severity
and feedback trends (not just colored borders), subtle motion on state
changes (loading, submitting feedback, severity badges), and a real
information hierarchy that leads with the single most important thing
on each screen (e.g. the highest-severity alert, not a flat list).

Concretely:

### 1. Design system first
`static/tokens.css` or equivalent: a real type scale (display/heading/
body/caption), a spacing scale, a considered color system (not just one
green — include a proper neutral gray ramp, semantic colors for
low/moderate/high/severe that are distinguishable and accessible —
check contrast), border-radius and shadow scale for depth. Pick and
load a real typeface pairing (Google Fonts is fine, self-host or link
with a documented CDN fallback) instead of the system font stack.

### 2. Dashboard / field list (`index.html`)
Redesign as a real landing view: a clear header/nav, a hero or summary
strip (e.g. "3 fields, 1 needs attention"), field cards with actual
visual weight differentiation (a field with a severe alert should look
urgent at a glance — icon, color, position — not just a thin colored
line), not a bare unstyled list.

### 3. Field detail (`field.html`)
This is the core screen. Redesign the crop recommendation / irrigation
advice / disease risk / advisory sections with real visual hierarchy —
consider a card-based or tabbed layout, icons per category (crop,
water, disease), a genuine severity indicator (e.g. a radial/gauge or
prominent colored badge, not just a border color), and present the
explanation (`summary_en`/`summary_kn`) in a way that reads as
"why we're telling you this," not a wall of text. If SHAP-style
feature contributions are available in the data passed to the
template, consider a simple horizontal bar visualization for the top
contributors — genuinely useful, not just decorative.

### 4. Feedback form
Make the 1-5 rating a real interactive control (star rating or similar,
not a bare number input/select), with clear success/error states and a
smooth micro-interaction on submit (loading state, success confirmation)
rather than a full page reload feeling static.

### 5. Responsive + accessibility pass
Must work well from ~360px mobile width up through desktop — this is
explicitly for farmers/field use on phones as well as evaluators on
laptops. Check color contrast (WCAG AA at minimum) especially for the
severity colors. Keyboard-navigable forms. Don't sacrifice
accessibility for visual flourish.

### 6. Light motion, used sparingly
CSS transitions/animations for: page load fade-in, card hover states,
severity badge emphasis, feedback submit confirmation. Nothing that
delays the user or feels gimmicky — motion should communicate state,
not decorate.

## Tests

No new backend logic, so no new unit/integration test *category* is
required — but:
- Re-run `pytest tests/api/` and confirm all existing tests still pass
  unmodified (or note+justify any that had to change, per the
  constraints above).
- If you add any client-side JS with actual logic (not just CSS
  transitions) — e.g. the star rating control, a tab switcher — add a
  minimal test or at least a manual verification note in the handoff;
  don't leave meaningfully-behaviored JS completely unverified.
- Acceptance checklist (its own section in the handoff):
  - [ ] All pre-existing `tests/api/` tests pass unmodified (or changes
        justified)
  - [ ] Dashboard, field detail, and feedback screens all screenshot
        cleanly at both a mobile width (~375px) and a desktop width
        (~1280px) — actually check this, don't assume
  - [ ] Severity is visually unambiguous at a glance (color + shape/
        icon, not color alone — colorblind-safe)
  - [ ] Feedback star rating and submit flow works end to end against
        the real API
  - [ ] No console errors in the browser for any of the three screens

## Update doctrine

`CLAUDE.md`, `PROGRESS.md` (note this as a follow-up to Module 14, not
a renumbered module — e.g. "Module 14b: UI/UX uplift"), commit and
push. `git pull` first in case Module 15 prep or anything else has
landed.

## Handoff format
```
Module: 14b — UI/UX Uplift
Status: complete | blocked
Tooling used: <Stitch CLI used / not available — details>
Design system summary: <fonts, palette, scale — brief>
Screens redesigned:
Files changed:
Commits made:
Existing tests: <pass/fail, note any changes and why>
New client-side behavior tested: <describe or "none added">
Acceptance checklist: <each item, checked or not, with a one-line note>
Known limitations:
Screenshots: <describe what you visually verified and how, since I can't
  see your screen — e.g. "captured via <tool> at 375px and 1280px,
  attached/described below">
Next recommended step: Module 15 — Integration, deploy, docs
```
