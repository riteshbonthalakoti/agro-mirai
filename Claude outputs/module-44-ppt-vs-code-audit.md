# MODULE 44 — Full PPT/docs-vs-code verification audit

Ritesh will paste `AGRO_MIRAI2.1.pptx` into this session directly. This
module is a verification audit only — no new features, no fixes beyond
what's explicitly listed in item 4 below. The goal is one honest answer
to one question: for every claim made in the PPT and in this repo's own
docs, is it actually implemented and actually working in the real code
and real deployed services today — not "should work," not "was true in
an earlier module," but true right now.

Read `CLAUDE.md` and `PROGRESS.md` at the repo root first if you haven't
already this session, so you're not re-deriving architecture from scratch.

## 1. Build the claim list

Go through `AGRO_MIRAI2.1.pptx` slide by slide and extract every concrete,
checkable claim: every feature named, every technology named (e.g.
"OpenWeatherMap," "SHAP-based explainability," "voice in Kannada"), every
number given (model accuracies, language count, etc.), every workflow
described (e.g. "farmer scans a leaf and gets a diagnosis"). Also pull
claims from this repo's own docs — `README.md`, `docs/architecture.md`,
`docs/PROJECT_WALKTHROUGH.md` if present, `specs/core/openapi.yaml`'s
documented endpoints, and `decisions/*.md`'s stated outcomes. Build one
flat checklist, each item phrased as a single testable claim (e.g. "the
app shows a crop recommendation with a SHAP-based explanation the farmer
can read in their own language").

Don't skip a claim because it sounds outdated or clearly wrong at a
glance — list it anyway and mark the verdict honestly. A stale claim in
the PPT that no longer matches the code is itself a real finding worth
reporting, not something to silently correct.

## 2. Verify each claim against the real, currently-deployed system

For each item on the checklist, do the real check, not a plausible-sounding
one:

- **Code claims** (a feature/logic exists): find the actual file and
  line(s) implementing it. Cite the path. If you can't find it, say so —
  don't assume it's "probably elsewhere."
- **Behavior claims** (a feature works end to end): hit the real deployed
  Render endpoint(s) involved with a real request and show the real
  response — status code and body, not a description of what it should
  return. For anything reachable only through the mobile app (UI flow,
  voice playback, camera scan), either drive it through a fresh Expo Go
  session yourself and report exactly what you saw, or — if that's not
  practical in this session — mark it "needs Ritesh to confirm on device"
  rather than inferring it works from the code alone.
- **Numeric claims** (model accuracies, test counts, etc.): check them
  against the actual committed eval reports (`docs/eval/*.json`) or a
  fresh test run — don't retype a number from a prior module's own
  changelog entry in `PROGRESS.md`/`CLAUDE.md` without confirming the
  underlying report file still says the same thing.
- **Infra claims** (which services exist, what's hosted where): check the
  real Render services via the Render CLI, not `render.yaml` alone —
  config can drift from what's actually deployed.

## 3. Produce one clear report, not a wall of raw output

Write `docs/PPT_VS_CODE_AUDIT.md` with one row per claim:

```
| # | Claim (from PPT / doc, cite source) | Verdict | Evidence |
|---|---|---|---|
```

Verdict is one of: **Confirmed working** (you personally verified it live
or found and can cite the exact working code), **Implemented but
unverified live** (code exists, but you couldn't personally confirm it
behaves correctly right now — say exactly why, e.g. "needs a real device
to test voice playback"), **Broken** (code exists but a real check showed
it failing — cite the actual error), **Not implemented** (no code found
for this claim), **Claim is stale/inaccurate** (the PPT or doc says
something the current architecture deliberately does differently, e.g.
Open-Meteo instead of OpenWeatherMap — note this isn't necessarily a bug,
just a documentation mismatch worth a one-line PPT correction).

End the report with a short summary: total claims, how many in each
verdict bucket, and the handful that matter most for a faculty demo or a
real farmer to trust the product.

## 4. Fix only what's cheap and unambiguous

If you find something in verdict "Broken" that's a small, obvious,
low-risk fix (a wrong env var, a stale config value, a one-line bug) — fix
it and note the fix in the report. For anything bigger, riskier, or
ambiguous, do NOT fix it in this module — just report it clearly with
enough detail that a future module can be scoped around it. This module's
job is an honest map of reality, not another round of feature work.

## What NOT to do

- Don't rewrite the PPT itself, redesign the UI, or retrain any model in
  this module — those are separate, later modules if needed.
- Don't mark anything "Confirmed working" without either a real command
  output/response you're showing, or an explicit note that it needs
  Ritesh's own device confirmation.
- Don't skip verifying something just because an earlier module or
  `PROGRESS.md` already claimed it was done — that's exactly the kind of
  claim this audit exists to re-check.

## Handoff format

```
Module: 44 — PPT/docs-vs-code verification audit
Status: complete | blocked

Report written to: docs/PPT_VS_CODE_AUDIT.md
Total claims checked: <N>
Confirmed working: <N>
Implemented but unverified live: <N> (list what needs Ritesh's device)
Broken: <N> (list, with real evidence)
Not implemented: <N>
Stale/inaccurate claims: <N>

Cheap fixes made this module: <list, if any>

Top issues Ritesh should know about before any demo or launch decision:
<3-5 bullet-free sentences, most important first>

Next recommended step:
```
