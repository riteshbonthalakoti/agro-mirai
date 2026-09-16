# MODULE 35 — Three standalone Colab notebooks (crop recommendation, irrigation, disease-risk) for Phase-II Review-1

Continuing AGRO MIRAI. This is not new product work — it's a presentation
deliverable. The team's faculty (per Sowjanya's message and the attached
Phase-II schedule) wants Review-1 (Week 9, Sep 21–26) to show: modules
completed, technologies used, working outputs/screenshots, test cases and
results, and a live Input → Processing → Output demonstration. The team
has real, working code already (this repo) but nothing in a form a
non-technical faculty member can open and see run. Three self-contained
Google Colab notebooks — one per real model already built in this
project — solve that: link-shareable, runnable top-to-bottom with one
click (Runtime → Run all), no setup, no backend/mobile app required.

Each notebook must use this project's **real, already-implemented logic**
— pull the actual feature-engineering and model code from `src/agro_mirai/`
rather than re-deriving anything from scratch, since the whole point is
proving what's already built, not writing new science.

## Notebook 1 — Crop Recommendation

- Source the real logic from wherever `GET /v2/fields/{id}/recommendation`
  gets its answer (the crop-suitability model/rules and its SHAP-based
  explanation, per `ExplanationService`).
- Structure: (1) Input — a real or realistic field profile (location,
  soil chemistry, recent weather) shown as a simple table; (2) Processing
  — the actual feature-building and model-scoring steps, with brief plain-
  English markdown explaining each step (not just code with no narration —
  this will be read by faculty, not just run); (3) Output — the
  recommended crop(s) plus the real SHAP/feature-importance explanation,
  rendered as a simple chart or table, not raw JSON.
- Include a short "why this matters" markdown cell up top and a results
  summary at the bottom — faculty reviewers skim, so the notebook should
  be readable even without running it.

## Notebook 2 — Irrigation Advisory

- Source the real ET0 water-balance logic behind
  `GET /v2/fields/{id}/irrigation` (Module 17/18's water-balance model).
- Same Input → Processing → Output structure: real/realistic weather +
  soil-moisture inputs (call out clearly that soil-moisture uses the
  documented typical-value fallback when real sensor data isn't
  available, per the project's own degrade-not-fail doctrine — don't
  hide this, it's a legitimate, documented design choice worth
  explaining, not a flaw to disguise), the real ET0 calculation steps
  shown clearly, and a real recommended irrigation depth as output.
- Show at least one sensitivity example (e.g. how the recommendation
  changes with more/less recent rainfall) — this demonstrates the model
  actually responds to real inputs, which is exactly what a reviewer
  will want to see live.

## Notebook 3 — Disease Risk Detection

- Source the real logic behind `GET /v2/fields/{id}/disease-risk` and the
  image-upload path, including the CNN-vs-environmental-fallback split
  that's already correctly implemented (per Module 21) — show both paths
  in the notebook if practical (a real image running through the CNN path
  if weights are available in this environment, and the rule-based
  environmental-fallback path either way), clearly labeled as two
  distinct, real methods, not glossed as one.
- Same Input → Processing → Output structure: a real leaf image as input,
  the actual preprocessing/feature steps, and the real risk output with
  its plain-language rationale.

## Shared requirements across all three notebooks

- Each notebook must actually run end-to-end in a fresh Colab runtime with
  no manual setup beyond `pip install` cells already included — test this
  for real (a fresh runtime, Run All, confirm it completes without manual
  intervention) before calling it done.
- No fabricated results — every number/output shown must come from
  actually running this project's real code against real or realistic
  data, not a hardcoded "example output" written by hand.
- Keep each notebook self-contained: don't require cloning the full
  private repo with credentials — either (a) install directly from a
  public pip-installable subset if one exists, (b) pull only the specific
  needed modules via a public raw-GitHub URL if the repo (or relevant
  files) can be made public/readable for this purpose, or (c) embed the
  minimal necessary code directly in the notebook, copied faithfully from
  the real source files (cite the source file/line at the top of each
  code cell so it's traceable back to the real implementation, not
  presented as if written fresh). Confirm with Ritesh which of these three
  is acceptable before choosing, since (b)/(c) touch repo-visibility
  decisions that aren't yours to make unilaterally.
- Add a title cell to each notebook stating clearly this is real code from
  the AGRO MIRAI capstone project, matching what module/feature it
  demonstrates, for faculty context.
- Keep the notebooks clean and presentation-ready: minimal debug print
  spam, clear section headers, one clear "Results" cell per notebook near
  the end that a reviewer's eye goes straight to.

## Also prepare (lighter lift, still real)

Since the team also needs to show progress against the schedule's own
"Implementation" and "Testing" headings (per Sowjanya's message), and per
Ritesh's own instruction not to bother filling in the recommended
Module/Status/Description table:

- A short, honest one-page summary (markdown, not the school's table
  format) of what's actually built and working today, written in plain
  language a non-technical faculty member and non-technical teammates can
  present confidently — pull this from the real, already-verified state
  of the project (Module 32-34's live-tested endpoints, the working
  mobile app, the real bug fixes), not aspirational claims. Explicitly
  separate "done and proven" from "in progress" — this project has
  genuinely substantial real work; the summary should reflect that
  honestly without either underselling it or claiming more than what's
  been live-verified this session.
- A short list of real test cases and results already available from this
  session's live testing (Module 32/33/34's real endpoint proofs, the
  real on-device test) that the team can present as their testing
  evidence — reuse real evidence already gathered rather than fabricating
  new test-case documentation.

## What NOT to do

- Don't build new product features in this module — this is a
  presentation/documentation task using what already exists.
- Don't fabricate screenshots, outputs, or results anywhere.
- Don't decide the repo-visibility question (public subset vs. embedded
  code) unilaterally — flag it and get Ritesh's call.

## Handoff format

```
Module: 35 — Colab notebooks + progress summary for Phase-II Review-1
Status: complete | blocked | needs-decision

Notebook 1 (Crop Recommendation): <link, confirmed runs end-to-end fresh>
Notebook 2 (Irrigation): <link, confirmed runs end-to-end fresh>
Notebook 3 (Disease Risk): <link, confirmed runs end-to-end fresh>

Repo-access approach used: <public subset / raw-URL fetch / embedded code
  — and why, or flagged as needing Ritesh's decision>

Progress summary: <attached/linked>
Test evidence reused: <what was pulled from prior live-tested modules>

Known limitations:
Next recommended step:
```
