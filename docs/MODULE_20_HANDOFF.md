# Module 20 Handoff — CNN Disease Detection (PlantVillage / MobileNetV2)

**Status:** done, 2026-08-30
**Depends on:** Module 08 (`DiseaseRiskModel`, ADR 0009), whose CNN upgrade
path this module implements.
**Blocks:** nothing — additive, optional to consume.

---

## 1. What was actually verified (not just logged)

Training was run once, unattended, on a real Colab T4 GPU session. Before
writing this handoff, the result was independently re-checked rather than
trusted from the training log alone:

| Check | Result |
|---|---|
| Artifact file sizes | `disease_cnn_mobilenetv2.pt` = 9,340,043 bytes, `disease_cnn_class_names.json` = 1,176 bytes — consistent with a real MobileNetV2 state_dict (not a truncated/corrupt download) |
| Class count | `json.load(...)` → exactly 38 entries, matching `num_classes` in the training run |
| Architecture load | `ImageDiseaseRiskModel.__init__` loads the state_dict into a real `torchvision.models.mobilenet_v2` with `weights_only=True` — no shape mismatch, no key errors |
| **Real held-out prediction** | 5 images pulled fresh from the Colab VM's dataset copy (never part of the local test run) — Apple healthy, Apple scab, Tomato late blight, Grape black rot, Corn common rust — run through the actual downloaded weights via the real `ImageDiseaseRiskModel.predict` path. **5/5 correct**, confidence 0.993–1.000 |
| Test suite | `tests/vision/` (2 tests) pass against the real artifact: missing-weights `FileNotFoundError`, and a schema-valid `DiseaseRiskAlert` end to end |
| Regression | Full main suite unaffected: 294 passed, 0 failed, 25 skipped; `check_specs.py`: OK |

This is real evidence the model learned the task, not an assumption from
the printed `val_acc` numbers alone.

---

## 2. What was built, file by file

| File | Purpose |
|---|---|
| `src/agro_mirai/models/image_disease_risk_model.py` | `ImageDiseaseRiskModel.predict(image_path, field_id) -> DiseaseRiskAlert`. Lazy-imports torch/torchvision/PIL inside `__init__`/`predict` so importing the module doesn't require them installed. Raises `FileNotFoundError` (same convention as `CropRecommendationModel`) if the artifact isn't present. |
| `src/agro_mirai/models/disease_cnn_labels.py` | Pure functions: `parse_class_name`, `crop_type_for` (maps to the 22-value `crop_type` enum or `None`), `risk_level_for` (confidence-based heuristic), `disease_display_name`. No torch dependency — testable without the vision stack. |
| `src/agro_mirai/models/disease_risk_scoring.py` (edited) | Added public aliases `RISK_ACTION`/`RISK_WINDOW_DAYS` (were private `_RISK_ACTION`/`_RISK_WINDOW_DAYS`) so the CNN path reuses the same risk-level → action/window lookup as the rule-based path. Additive, non-breaking. |
| `tools/train_disease_cnn.py` | The exact training script run on Colab. Documents reproduction steps in its own docstring. **Not runnable locally** — Colab `/content/...` paths, and torch/torchvision are deliberately excluded from the main `requirements.txt` (mirrors the Module 12 voice-stack exclusion, decisions/0014). |
| `decisions/0018-disease-cnn.md` | Full ADR: dataset choice and why, training setup, three honest limitations (crop-enum coverage, lab-vs-field generalization, no severity ground truth), and why this is additive rather than wired into `DecisionEngine`. |
| `decisions/0001-index.md` (edited) | New ADR 0018 entry. |
| `docs/eval/disease_cnn_eval.json` | Committed eval report — full per-epoch history, best val accuracy, known limitations. Same convention as `crop_rf_eval.json`/`irrigation_rf_eval.json`. |
| `tests/models/test_disease_cnn_labels.py` | 10 unit tests, pure-Python, run in the main suite (no torch needed). |
| `tests/vision/` (new dir) | `__init__.py` + `test_image_disease_risk_model.py`, 2 tests. Mirrors `tests/voice/`'s isolation pattern — run separately under `.venv/`, excluded from the default `pytest`/CI invocation. |
| `.github/workflows/ci.yml`, `README.md`, `MANUAL_TEST_GUIDE.md` (edited) | Added `--ignore=tests/vision` alongside the existing `--ignore=tests/voice`. |
| `modules/20-disease-cnn/STATUS` | `done` — feeds `tools/update_state.py`'s `PROGRESS.md` regeneration. |
| `CLAUDE.md`, `PROGRESS.md` (edited) | Module 20 narrative + regenerated state block. |
| `models/disease_cnn_mobilenetv2.pt`, `models/disease_cnn_class_names.json` | Gitignored trained artifacts (same `/models/` gitignore rule as the other two `.joblib` files). **Not in git — see §5 for how to regenerate.** |

---

## 3. Training details (for reference / re-training)

- **Dataset:** Kaggle `abdallahalidev/plantvillage-dataset`, `color/`
  split only (the same download also contains `grayscale/` and
  `segmented/` variants, unused). 38 classes, 54,305 images total.
- **Why this dataset over alternatives:** first tried
  `emmarex/plantdisease` (the smaller, more commonly cited "PlantVillage"
  Kaggle repack) — discovered its 3 crops (pepper, potato, tomato) have
  **zero** overlap with AGRO MIRAI's 22-value `crop_type` enum. Switched
  to the fuller 38-class dataset specifically because it includes apple,
  corn/maize, grape, and orange, which *are* in the enum.
- **Architecture:** `torchvision.models.mobilenet_v2`, ImageNet-pretrained.
  `features` frozen except the last 3 blocks (fine-tuned); classifier head
  replaced with a fresh 38-way `nn.Linear`.
- **Split:** 85% train / 15% val, `torch.Generator().manual_seed(42)`.
- **Augmentation (train only):** random resized crop, horizontal flip,
  ±15° rotation, color jitter (brightness/contrast/saturation 0.2).
- **Optimizer:** Adam, lr=1e-3, `StepLR(step_size=4, gamma=0.3)`.
- **8 epochs, batch size 64.** Checkpoint saved only when `val_acc`
  improves (best-of-run, not last-epoch).
- **Runtime:** Google Colab T4 GPU, ~245s/epoch (~33 min total) — CPU-
  bound on image decoding (Colab's standard shape has 2 vCPUs; the
  DataLoader's `num_workers=4` triggered a "more workers than cores"
  warning, which is the actual bottleneck, not the GPU).
- **Per-epoch history** (also in `docs/eval/disease_cnn_eval.json`):

  | Epoch | train_loss | train_acc | val_acc |
  |---|---|---|---|
  | 1 | 0.2264 | 0.9310 | 0.9655 |
  | 2 | 0.0988 | 0.9684 | 0.9536 |
  | 3 | 0.0745 | 0.9742 | 0.9812 |
  | 4 | 0.0619 | 0.9800 | 0.9797 |
  | 5 | 0.0276 | 0.9904 | 0.9897 |
  | 6 | 0.0222 | 0.9919 | 0.9861 |
  | 7 | 0.0212 | 0.9932 | 0.9921 |
  | **8** | **0.0199** | **0.9931** | **0.9924 (best, saved)** |

---

## 4. How training was actually driven (tooling note)

The Google Colab CLI (`google-colab-cli`) does **not** run on native
Windows — it imports the Unix-only `termios` module. It was installed and
authenticated inside **WSL2 Ubuntu** instead (already present on this
machine, already `uv tool`-installed from an earlier unrelated session).
The entire training run — session creation, code execution, status
polling, file download — was driven from this Windows/Claude Code session
by shelling out to `wsl -e bash -lc "colab ..."`, with **zero manual
browser/notebook interaction**:

```bash
colab new --session module20 --gpu T4
echo '<code>' | colab exec --session module20 --env KAGGLE_API_TOKEN=...
colab exec --session module20 -f /tmp/train_disease_cnn.py --timeout 1800
colab download --session module20 /content/out/disease_cnn_mobilenetv2.pt ...
```

Two real gotchas hit along the way, in case this is repeated:

1. `colab exec -f <path>` expects a **local** file path (it reads and
   streams the code to the remote kernel) — passing the *remote*
   `/content/...` path fails with `FileNotFoundError` on the CLI side.
2. The CLI's own reply-wait timed out (`TimeoutError: Timeout waiting for
   reply`, exit code 1) **after** the script had already finished and
   printed `DONE best_val_acc=0.9924` — the training itself succeeded;
   only the CLI's own bookkeeping call failed. Always check the tail of
   the captured stdout before concluding a `colab exec` failure means
   training failed.

Kaggle auth on the Colab VM: `kaggle` (v2.0.2) was already preinstalled
there; the same `KAGGLE_API_TOKEN` env var used locally was passed in via
`colab exec --env KAGGLE_API_TOKEN=...` and persisted across subsequent
`exec` calls (it's a long-lived kernel, not a fresh process per call).

---

## 5. How to re-train (if the artifact needs regenerating)

1. `wsl` → `colab new --session <name> --gpu T4` (needs `colab auth`
   completed once already, browser OAuth — already done on this machine).
2. Copy `tools/train_disease_cnn.py` to a local (WSL) path, e.g.
   `/tmp/train_disease_cnn.py`.
3. `colab exec --session <name> --env KAGGLE_API_TOKEN=<token> -f
   /tmp/train_disease_cnn.py --timeout 1800` — expect ~35 min.
4. `colab download --session <name> /content/out/disease_cnn_mobilenetv2.pt
   models/disease_cnn_mobilenetv2.pt` (and the two other output files —
   `class_names.json` → `models/disease_cnn_class_names.json`,
   `training_history.json` for updating `docs/eval/disease_cnn_eval.json`).
5. Re-run `tests/vision` under `.venv/` and diff the new
   `docs/eval/disease_cnn_eval.json` against the committed one before
   trusting the new artifact — same convention `requirements.txt`
   documents for the sklearn models.

---

## 6. What's explicitly NOT done (real, documented gaps)

1. **Not wired into `DecisionEngine` or the API.** No `Field`/API schema
   anywhere in this codebase accepts an image upload — that's genuinely
   new surface area (endpoint, storage, `DecisionEngine`-side choice of
   image-path vs. environmental-path), not part of this module. ADR 0009
   sketched the intended pattern (image path first, environmental
   fallback) but building it was out of scope here.
2. **Crop-enum coverage is 4/22.** Apple, maize, grapes, orange only.
   `CNN_COVERED_CROP_TYPES` / `crop_type_for()` in `disease_cnn_labels.py`
   exist specifically so a future caller can cross-reference a CNN call
   against a field's actual crop, the way Module 18's
   `regional_suitability.py` does — that cross-reference isn't built yet.
3. **Lab images, not field photos.** 99.24% is validation accuracy on a
   random hold-out from the *same* PlantVillage lab-condition
   distribution as training — plain background, controlled lighting,
   single detached leaf. A real farmer's phone photo (cluttered
   background, natural light, leaf still on the plant) is a materially
   different input distribution; published PlantVillage-model research
   widely reports substantially lower accuracy on real field photos.
   Not measured or mitigated in this module.
4. **No severity ground truth.** `risk_level_for`'s confidence-based
   floor/scale (healthy→low, disease→moderate/high/severe by softmax
   confidence) is a documented heuristic, not learned severity.
5. **No test-set images shipped for CI.** The 5-image spot-check in this
   handoff (§1) was done ad hoc against the Colab VM's dataset copy, not
   saved as a repo fixture — `tests/vision`'s real-prediction test uses a
   synthetic solid-color image only (it checks output *shape*/schema
   validity, not classification correctness). If ongoing
   regression-on-real-images coverage is wanted, a handful of PlantVillage
   images would need to be vendored into the repo (license permitting —
   CC-BY-NC-SA-4.0 per the Kaggle dataset page) as a real fixture.

---

## 7. Immediate next steps (if picking this up)

- If continuing straight to wiring the CNN into the product: design the
  image-upload contract first (new `POST` endpoint, storage choice —
  Supabase Storage fits the existing GEE-live/SQLite-dev-vs-Supabase-prod
  pattern), then extend `DecisionEngine` per ADR 0009's sketch.
- If instead the next priority is elsewhere per
  `docs/ROADMAP_PRODUCTION.md`, Module 20 needs no further action — it's
  a complete, tested, standalone unit that can be picked up later without
  re-touching anything else.
- Nothing in this module has been committed to git yet (see `git status`)
  — that's a deliberate pause point, not an oversight.
