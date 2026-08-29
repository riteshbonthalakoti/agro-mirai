# AGRO MIRAI — Manual test-drive guide (Modules 01–14b)

Everything below is run on your own machine, in your own terminal, from
`C:\Projects\AGRO MIRAI`. Two Python environments exist in this repo and
they serve different purposes — don't mix them up:

- **Global interpreter** (`python`, whatever's on your PATH) — used for
  the API/web app. Has Flask, scikit-learn, SHAP, etc.
- **`.venv`** (pinned to `transformers==4.49.0`) — used only for the
  Module 12 voice stack (AI4Bharat models). The global interpreter has
  `transformers` 5.x, which is incompatible with those models.

Open **two separate terminal windows/tabs** — one for each environment
— since you'll likely want the API server running in one while poking
at things in the other.

---

## 0. One-time setup check

In PowerShell or Command Prompt, from `C:\Projects\AGRO MIRAI`:

```powershell
cd "C:\Projects\AGRO MIRAI"
python --version          # should be 3.x, whatever's on your global PATH
git log --oneline -5      # sanity check you're on the latest commit
```

You should see `5efc96f Module 14b: UI/UX uplift...` at the top (or
later, if you've run more modules since).

### Install what the API/web app needs (global interpreter)

There's no committed `requirements.txt` yet (worth asking Claude Code
to generate one via `pip freeze` in Module 15 — flag it, don't just
work around it silently). For now:

```powershell
pip install flask scikit-learn shap joblib pandas numpy
```

If anything else is missing when you run tests, the traceback will
name the exact package — `pip install <name>` and continue.

---

## 1. Set up your `.env`

Copy `.env.example` to `.env` (a `.env` already exists in this repo from
earlier module work — check it first before overwriting):

```powershell
type .env
```

It needs, at minimum, for local testing:

```
FLASK_ENV=development
DATABASE_URL=agro_mirai_demo.db
API_KEY=demo-secret-key-123
FARMER_ID=11111111-1111-4111-8111-111111111111
```

That `FARMER_ID` is the real farmer from the `farm-001` fixture (Ravi
Kumar, Bellary, Karnataka) — using it means every screen and endpoint
will show real, non-empty data. Leave `SUPABASE_URL`/`SUPABASE_KEY` and
`EE_SERVICE_ACCOUNT_KEY` blank/unset for local testing — SQLite and the
NDVI cache fallback don't need them.

---

## 2. Seed the database with the golden fixture

This loads `farm-001` (Ravi Kumar, one field "North Plot", plus its
weather/soil/NDVI/model-output history) into a fresh SQLite file so the
app has real data to show you.

```powershell
python tools\seed_fixture.py --backend sqlite --db-path agro_mirai_demo.db
```

You should see it load each record type and finish with a round-trip
verification (no diff/mismatch output = success). If it errors on an
import, that's the moment to `pip install` whatever it names.

Make sure `.env`'s `DATABASE_URL` matches the `--db-path` you just used
(`agro_mirai_demo.db` above).

---

## 3. Start the Flask app

```powershell
$env:FLASK_APP = "agro_mirai.api.app:create_app()"
$env:PYTHONPATH = "src"
flask run --port 5000 --without-threads
```

(Command Prompt instead of PowerShell: use `set FLASK_APP=...` and
`set PYTHONPATH=src` on separate lines instead of `$env:...=`.)

Leave this terminal running — it's your live server. You should see
Flask's startup banner and `Running on http://127.0.0.1:5000`.

> **Note on `--without-threads`:** without this flag you'll hit
> `sqlite3.ProgrammingError: SQLite objects created in a thread can
> only be used in that same thread` on almost every request. This is a
> real bug in `SQLiteDataStore` (it opens one connection at app-start
> time, but Flask's threaded dev server dispatches each request on a
> different thread). `--without-threads` works around it for local
> testing; it needs a real fix before Module 15's deploy step, since
> a production WSGI server (multi-worker) will hit the same problem
> even worse. See the fix-up prompt for Claude Code.

---

## 4. Test the web frontend (Modules 11 + 14 + 14b) in your browser

Open **http://127.0.0.1:5000/** in a real browser (Chrome/Edge/Firefox)
— this is the actual place to judge the Module 14b redesign, not code
review.

Walk through:

1. **Dashboard** (`/`) — should show "Welcome, Ravi Kumar", the hero
   stat strip (fields tracked, hectares), and a field card for "North
   Plot" with the leaf icon.
2. **Resize your browser window** down to ~375px wide (or open dev
   tools → device toolbar → pick a phone) — confirm nothing overflows
   horizontally and it still reads cleanly.
3. Click into **North Plot** — the field detail page. Confirm crop
   recommendation, irrigation advice, and disease risk sections all
   show real values (not blank/error), each with a distinct icon and
   color per severity (not just a colored line).
4. Read the **explanation text** under each recommendation — this is
   Module 09's SHAP/rule-weight output surfacing as a human-readable
   sentence. If Kannada text (`summary_kn`) appears anywhere, that's
   Module 12's translation pipeline working end to end.
5. Scroll to the **feedback form** — pick a star rating, optionally add
   a comment, submit. Confirm you get a "Thanks — your feedback was
   recorded" confirmation, not a page error.
6. Open your browser's **DevTools console** (F12) while doing all of
   the above — confirm no red errors.

---

## 5. Test the API directly (Module 11) — without the browser

In your second terminal (server still running in the first), with
`API_KEY` matching what's in your `.env`:

```powershell
$KEY = "demo-secret-key-123"
$FIELD = "22222222-2222-4222-8222-222222222222"   # North Plot's id

# Liveness — no auth needed
curl.exe http://127.0.0.1:5000/health

# Farmer profile
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/farmers/me

# List fields
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields

# One field
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/$FIELD

# The three core recommendations (Modules 06/07/08 through the API)
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/$FIELD/recommendation
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/$FIELD/irrigation
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/$FIELD/disease-risk

# Full unified advisory (Module 10's DecisionEngine, end to end)
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/$FIELD/advisories

# Auth checks — both of these should return 401
curl.exe http://127.0.0.1:5000/farmers/me
curl.exe -H "Authorization: Bearer wrong-key" http://127.0.0.1:5000/farmers/me

# Unknown field — should be 404, not 500
curl.exe -H "Authorization: Bearer $KEY" http://127.0.0.1:5000/fields/00000000-0000-0000-0000-000000000000
```

Every response should be real JSON with actual model output — crop
name, irrigation urgency/depth, disease risk level, and (in the
advisory) an `explanation` block. If you get a 500, copy the traceback
from the Flask terminal — that's a real bug, not something to paper
over.

---

## 6. Test the feedback loop (Module 13)

Submit a couple more feedback entries through the web form (step 4.5
above), then, in your second terminal:

```powershell
python tools\feedback_report.py --db agro_mirai_demo.db --farmer-id 11111111-1111-4111-8111-111111111111
```

This prints the aggregated report — counts, average rating, helpful
rate, broken down by severity/field. Confirm the numbers reflect what
you actually submitted. You can also try the pure synthetic demo mode,
which doesn't need a seeded DB at all:

```powershell
python tools\feedback_report.py --seed
```

---

## 7. Test the voice stack (Module 12) — separate terminal, `.venv`

This is the one part that needs the pinned environment. In a **fresh**
terminal:

```powershell
cd "C:\Projects\AGRO MIRAI"
.venv\Scripts\activate
python -m pytest tests\voice\ -v
```

This runs real inference against the checked-in sample audio
(`tests/voice/fixtures/en_sample.wav`, `kn_sample.wav`) — speech-to-
text, translation (IndicTrans2), and text-to-speech (Piper for English,
vits_rasa_13 for Kannada). First run will be slow (models download from
Hugging Face the first time); subsequent runs use the local cache.

To actually **hear/see it work interactively** rather than just watch
tests pass, drop into a Python shell in the same activated `.venv`:

```powershell
python
```

```python
import sys
sys.path.insert(0, "src")
from agro_mirai.voice.ai4bharat_voice import AI4BharatVoiceService

svc = AI4BharatVoiceService()

# Translate an advisory summary into Kannada
kn_text = svc.translate("Your soil moisture is low. Irrigate today.", "en", "kn")
print(kn_text)

# Speech-to-text on the checked-in Kannada sample
with open("tests/voice/fixtures/kn_sample.wav", "rb") as f:
    audio_bytes = f.read()
transcript = svc.speech_to_text(audio_bytes, "kn")
print(transcript)

# Text-to-speech — writes audio bytes back; save and play them
audio_out = svc.text_to_speech(kn_text, "kn")
with open("kn_output.wav", "wb") as f:
    f.write(audio_out)
```

Then just open `kn_output.wav` in Windows Media Player or any audio app
to actually hear the generated Kannada speech. This is the most
convincing single thing you can show a VTU evaluator — real Kannada
TTS coming out of a model running on your own laptop, no internet
dependency.

(Note: the web frontend doesn't have a "listen in Kannada" button wired
up yet — that's a documented, known limitation from Module 14b, not a
bug. The voice pipeline itself works; it's just not exposed through the
UI yet. Worth deciding if you want that wired in before Module 15.)

---

## 8. Run the full automated test suite yourself

Back in the global-interpreter terminal:

```powershell
python -m pytest --ignore=tests\voice -q
```

This should show everything green except intentional skips (things
like `shap` or optional deps, if not installed globally). Then, in the
`.venv` terminal:

```powershell
python -m pytest tests\voice -q
```

Between the two runs you've now independently exercised every module
01 through 14b — not just read a Claude Code handoff claiming it works.

---

## Quick reference — what to look at per module

| Module | What to check | Where |
|---|---|---|
| 01–02 | Doctrine exists, contract-first discipline | `CLAUDE.md`, `specs/core/openapi.yaml` |
| 03 | Weather/NDVI/soil adapters | `pytest tests/acquisition -q` |
| 04 | Storage layer, golden fixture | Step 2 above (seed script) |
| 05 | Feature pipeline | `pytest tests/features -q` |
| 06 | Crop recommendation | `/fields/{id}/recommendation` (step 5) |
| 07 | Irrigation prediction | `/fields/{id}/irrigation` (step 5) |
| 08 | Disease risk (MVP, rule-based) | `/fields/{id}/disease-risk` (step 5) |
| 09 | Explainability (SHAP + rule-weight) | `explanation` field in `/advisories` output |
| 10 | Decision engine (unified advisory) | `/fields/{id}/advisories` (step 5) |
| 11 | Flask API layer | All of step 5 |
| 12 | Voice/language | Step 7 |
| 13 | Feedback loop | Step 6 |
| 14 + 14b | Web frontend | Step 4 |
| 16 | CI, Sentry, rate limiting, backups | `/health`, `.github/workflows/ci.yml` |
| 17 | ET0-based irrigation water balance | `/fields/{id}/irrigation`'s `rationale` field cites ET0/ETc/deficit |
| 18 | Regional crop-suitability sanity layer | `out_of_region`/`regional_alternative` in `/fields/{id}/recommendation` |
| 19 | Multi-tenant `/v2` auth + read-only Admin | Step 8 below |

## Step 8 — Module 19: `/v2` multi-tenant auth + Admin (new, `/v1` above is unaffected)

Everything in steps 1–7 above still exercises the original `/v1`
single-shared-`API_KEY` flow, which **stays alive unmodified** —
`decisions/0017-multi-tenant-v2.md` made that an explicit decision, not
an accident, so this guide's earlier steps don't go stale.

`/v2` is a separate, real login/session system, additive alongside it:

```bash
# Register a farmer (real password-strength validation — try "a" and
# watch it get rejected with a 400, not silently accepted).
curl -s -X POST http://localhost:5000/v2/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"Sup3rSecret1","name":"Your Name","preferred_language":"en"}'

# Log in — issues a signed session cookie (curl: -c/-b to persist it).
curl -s -c cookies.txt -X POST http://localhost:5000/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"Sup3rSecret1"}'

# Access your own data using the session cookie, no API key needed.
curl -s -b cookies.txt http://localhost:5000/v2/fields

# Log out — the same cookie stops working afterward.
curl -s -b cookies.txt -X POST http://localhost:5000/v2/auth/logout
```

**Admin dashboard** (read-only — list farmers/fields, system-wide
feedback aggregates, genuinely no write action anywhere on this
surface): register an account as above, then promote it to admin
out-of-band (there is no self-service admin signup, by design):

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
store = SQLiteDataStore('agro_mirai.db')
f = store.get_farmer_by_email('you@example.com')
f.role = 'admin'
store.save_farmer(f)
"
```

Then visit `http://localhost:5000/admin/login` in a browser (server-
rendered Jinja2, same stack as the Module 14 frontend — minimally
styled, labeled "functional, not yet polished" on the page itself), or
hit the JSON equivalents directly: `GET /v2/admin/farmers`,
`GET /v2/admin/fields`, `GET /v2/admin/feedback` (with the session
cookie from logging in as the admin account above).

If anything in here breaks in a way that doesn't match what a
handoff claimed, that's exactly the kind of thing to bring back to me
— I'll re-verify against the actual repo state rather than take either
of our first impressions at face value.
