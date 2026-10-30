# Running Agro Mirai locally

This covers everything needed to run the app on your own machine for a demo/evaluation: the backend API, the landing page, the admin dashboard, and the mobile app. **This is local-only.** It does not touch or require the live production deployment (Render backend, Vercel landing page, Supabase production database) — those run independently and are documented separately. Nothing you do here affects production.

If you're pasting this into an AI coding assistant to have it set everything up for you, paste this whole file as-is — every command below is meant to be run exactly as written, in order, and has been verified against the actual repository.

---

## Prerequisites

Install these first:

- **Python 3.12** — https://www.python.org/downloads/
- **Node.js 20+** — https://nodejs.org/
- **Git** (only needed for the git-clone path below, not the ZIP path) — https://git-scm.com/downloads
- **Android Studio** (for the mobile app — Android emulator + SDK) — https://developer.android.com/studio

**A note on "Expo Go":** plain Expo Go (the generic app from the Play Store) is **not enough** for this project. The app uses native modules Expo Go doesn't ship with — `@maplibre/maplibre-react-native` (the map), a custom native module for SMS OTP autofill (`mobile/modules/sms-retriever`), and several native config plugins (release signing, cleartext traffic, a pinned JDK). You need the project's own "dev client" build instead — a one-time 10-20 minute build, covered in step 5 below, after which every day-to-day run is exactly as fast as Expo Go.

---

## 1. Get the code

**Option A — git clone (recommended if available):**
```bash
git clone <repo-url>
cd agro-mirai
```

**Option B — plain ZIP download (no git required):**
1. Download the ZIP from the repo's "Code → Download ZIP" button (or whatever link you were sent).
2. Extract it anywhere on your machine.
3. Open a terminal in the extracted folder (the one containing `src/`, `mobile/`, `web/`, etc.) and treat that as your working directory for every command below.

---

## 2. Backend API (Python)

```bash
# From the repo root
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in `requirements.txt` (the app's real runtime dependencies) plus `pytest`/`pytest-asyncio` for the test step below.

```bash
# Seed a local SQLite database with test farm data
python tools/seed_fixture.py --backend sqlite --db-path agro_mirai.db

# Copy the example environment file and fill in your own keys
cp .env.example .env
```

Open `.env` and fill in whatever API keys you have (OpenRouter, Groq, Sarvam, etc. — see the comments in `.env.example` for what each one is for). The app runs fine with SQLite and zero AI keys configured: features that need an external AI call just return an honest "unavailable" response instead of crashing, which is completely fine for local UI/UX work or a demo that focuses on the app flow rather than every AI feature.

Start the backend:

```bash
PYTHONPATH=src python -m flask --app agro_mirai.api.app:create_app run
```

It runs at `http://localhost:5000`. Leave this terminal open — everything else below talks to it.

**Run the tests** (optional, confirms your setup is correct):
```bash
PYTHONPATH=src pytest --ignore=tests/voice --ignore=tests/vision --ignore=services/
```

---

## 3. Landing page (static site)

No build step — it's plain HTML/CSS/JS.

```bash
cd web/landing
python -m http.server 8080
```

Open `http://localhost:8080` in a browser. (The live production version of this page is deployed to Vercel and serves the real APK from Vercel Blob storage — none of that applies locally; this just serves the same static files from your disk.)

---

## 4. Admin dashboard

```bash
cd web/admin
BACKEND_URL=http://localhost:5000 node dev-server.mjs
```

Open `http://localhost:3100` in a browser. This is a small local stand-in for the Vercel rewrites the production site uses: it serves the dashboard's static files and forwards any `/admin`, `/v2`, or `/health` request to your local backend from step 2 (keeping everything same-origin, which matters for the session cookie), so make sure that backend is already running first.

---

## 5. Mobile app (Expo)

### One-time setup: build the dev client

```bash
cd mobile
npm install
```

**Android (emulator, or a real device connected via USB with "USB debugging" enabled):**
```bash
npx expo run:android
```

This builds and installs the dev client app on your emulator/device. It takes a while the first time (10-20 minutes) — that's normal; it's doing a real native Android build, not downloading a prebuilt binary.

### Every time after that: just start the dev server

```bash
cd mobile
npx expo start --dev-client
```

This prints a QR code and a URL. With the dev client app already installed (from the one-time step above):
- **Physical device**: open the dev client app on the phone — it connects automatically if the phone is on the same WiFi network as your computer, or scan the QR code with it.
- **Emulator**: press `a` in the terminal to open it there directly.

Any time you edit a `.ts`/`.tsx` file, the app updates live — no rebuild, no reinstall. You only need to repeat the `npx expo run:android` step if a *native* dependency changes (a new native module, a new Expo plugin) — ordinary feature work never requires it.

### Connecting the mobile app to your local backend

By default the app talks to the production backend. To point it at your local backend instead:

```bash
EXPO_PUBLIC_USE_LOCAL_BACKEND=true npx expo start --dev-client
```

Your phone/emulator and your computer must be on the same network for this to work (an emulator running on the same machine as the backend works automatically via `10.0.2.2`; a physical device needs the same WiFi).

---

## 6. Everything running together

A typical local demo session, four terminals:

| Terminal | Command | URL |
|---|---|---|
| 1 | Backend (`flask run`, from step 2) | http://localhost:5000 |
| 2 | Landing page (`python -m http.server 8080`, step 3) | http://localhost:8080 |
| 3 | Admin dashboard (`node dev-server.mjs`, step 4) | http://localhost:3100 |
| 4 | Mobile (`npx expo start --dev-client`, step 5) | QR code / emulator |

Start them in that order — the backend first, since both the dashboard and the mobile app talk to it, and the admin dashboard's proxy will show "backend unreachable" until it's up.

---

## Opening the project in VS Code

```bash
code .
```

Recommended extensions (VS Code will usually prompt for these automatically):
- Python
- ESLint
- Prettier

Each of the four pieces above can run in its own VS Code integrated terminal tab simultaneously — open a new terminal (`` Ctrl+` `` then the `+` icon) for each one.

---

## If something doesn't work

- **Backend won't start / import errors**: double-check you activated the virtual environment (`.venv\Scripts\activate` or `source .venv/bin/activate`) in *that* terminal before running `pip install` or `flask run` — a fresh terminal tab doesn't inherit it.
- **Admin dashboard shows "backend unreachable"**: the backend (terminal 1) isn't running, or isn't on port 5000. Confirm `http://localhost:5000/health` returns something in a browser first.
- **Mobile app can't reach the local backend**: confirm `EXPO_PUBLIC_USE_LOCAL_BACKEND=true` was set on the *same* command that started `expo start`, and that your phone and computer are genuinely on the same WiFi network (not one on mobile data).
- **`npx expo run:android` fails**: almost always an Android Studio/SDK setup issue, not a project issue — open Android Studio once first, let it finish its own first-run setup (SDK download, licenses), then retry.
