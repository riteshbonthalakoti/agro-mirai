# Module 39 — Manual test guide (rebuilt app)

Claude ran no servers and did not test on a phone. Type-check (`tsc`) and an
Android Metro bundle build pass; backend tests for new routes pass. NOTHING
below is "confirmed" until you see it. Report with the template at the end.

## A. Setup

Phone and PC on the SAME Wi-Fi.

### Terminal 1 — backend (use GLOBAL python, NOT .venv)
The `.venv` has no `earthengine-api` (satellite NDVI would silently fail);
global Python 3.12 has it plus everything else.
```powershell
cd "C:\Projects\AGRO MIRAI"
$env:PYTHONPATH = "src"
python -m flask --app agro_mirai.api.app:create_app run --host 0.0.0.0 --port 5000
```
- `--host 0.0.0.0` is required. The OTP code prints in THIS terminal.
- `.env` points at real Supabase, so accounts/fields are real rows.

### Terminal 2 — Expo
```powershell
cd "C:\Projects\AGRO MIRAI\mobile"
npx expo start --go --clear
```
Scan the QR with Expo Go. If Expo Go says SDK 57 is unsupported, use the
dev-client APK under `mobile\android\app\build\outputs\apk\debug\` and run
`npx expo start --dev-client --clear`. Say which you used.

### Firewall (admin PowerShell, only if phone can't connect)
```powershell
New-NetFirewallRule -DisplayName "AgroMirai Flask 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private,Public
New-NetFirewallRule -DisplayName "AgroMirai Metro 8081" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow -Profile Private,Public
```

### Step 0 — before opening the app
Phone browser → `http://<PC-IP>:5000/health` (PC IP: `ipconfig | findstr IPv4`).
Must return JSON. If not, fix network first.

### Clean slate
Expo Go → App info → Storage → Clear data. Use a phone number never used
before. (The app's Me tab shows the server URL it is talking to.)

## B. What changed (so you know what to look for)

The whole mobile app was rewritten: plain white, one green accent, system
font, 5 tabs: Home · Field data · Advice · Scan leaf · Me. New backend route
`GET /v2/fields/{id}/data-summary` so weather/soil/NDVI can be shown at all.
Old app never rendered weather, soil, NDVI, or the model crop pick.

## C. Test steps (stop at first FAIL, report)

Write down what you SEE, not what you expect.

1. **Language** — first screen: pick a language → Continue.
2. **Login** — name + 10-digit phone → Send code. Read the 6-digit code in
   Terminal 1 (`agro_mirai.auth.otp: OTP for +91…`). Enter → Verify.
   SEE: lands on "Add your first field".
3. **Add field** — name, area, "Use my location" (or type lat/lon; Bellary
   ≈ 15.14, 76.92), sowing date (default today, format YYYY-MM-DD), soil,
   crop. Save. Takes ~5–10 s (weather+soil fetched live).
   SEE: goes to Home, no error.
4. **Home tab — the three models** (pull down to refresh):
   - Crop recommendation: crop name, confidence %, other options, "Why this?"
     text; possibly an "not commonly grown in your region" note.
   - Irrigation: mm to apply, urgency badge, best window, "Why this?"
     (ET0 / rain numbers).
   - Disease risk: finding, risk badge, confidence, source, action.
   Each card has its own error + Retry; note exact error text if any.
5. **Field data tab** — tap "Refresh field data".
   - Weather: latest reading, forecast days, recent days, source name.
     Sanity-check temperature against your phone's weather app.
   - Soil: pH, N/P/K, organic carbon, moisture + source (soilgrids etc.).
   - Satellite NDVI: value + satellite + source, OR "still being fetched".
     Wait ~1 min, pull to refresh (auto re-checks at 20 s and 45 s).
   NDVI for a random new field only works if Earth Engine live works
   (source `gee_live`). If it never appears, paste Terminal 1's `ndvi` lines.
6. **Advice tab** — advisories list (severity badge, English body).
   - Listen: server voice is NOT running, so expect the note "Server voice
     unavailable — using your phone voice (English)" and phone TTS. Silence = bug.
   - "Was this useful?": stars + Helpful → Send → "Thanks".
   - "Ask by voice": tap, allow mic, speak, tap stop. Expect the unavailable
     message (voice/AI services not running) — that's the honest result today.
7. **Scan leaf** — take photo or pick from gallery.
   SEE: image, result, risk badge, and source label. Expected today:
   "Based on your farm's conditions (photo analysis unavailable)" because the
   CNN service isn't running. Scan appears in "Recent scans".
8. **Me tab** — change name → Save; change photo; switch language
   (kn/te/hi): UI text changes, crop/soil names translate. Edit a field
   (change crop / sowing date) then check Home updates. Add a 2nd field and
   switch between them. Report a problem. Sign out.
9. **Re-login** — same phone, new code from Terminal 1. Field still there.
10. **Offline** — Wi-Fi off, reopen app: offline banner + last saved data.

## D. Known limits (not bugs to report as new)
- Advisory body and "Why this?" text are English from the backend; UI says so
  for non-English. Only audio is translated (needs voice service).
- Kannada/Telugu/Hindi text for NEW strings is machine-written; tell me any
  wrong words.
- Voice (TTS/STT/ask) and CNN photo model need the separate services running;
  not started in this test.
- Models were saved with scikit-learn 1.7.2 and load under 1.4.2 with a
  warning in Terminal 1. If predictions look absurd, tell me — retrain fix:
  `python tools/train_crop_model.py` and `python tools/train_irrigation_model.py`.

## E. Report template
```
Path: Expo Go | dev-client APK
Step 0 /health from phone: PASS/FAIL
1 Language: 
2 Login/OTP: 
3 Add field: 
4 Home – crop rec (crop, %, why?): 
4 Home – irrigation (mm, urgency): 
4 Home – disease risk (label, source): 
5 Weather / Soil / NDVI: 
6 Advice (listen note, feedback, ask): 
7 Scan (result + source label): 
8 Me (profile, language, edit/delete field, bug report): 
9 Re-login: 
10 Offline: 
Red/error lines from Terminal 1 (paste): 
UI: still too busy? which screen? 
```
