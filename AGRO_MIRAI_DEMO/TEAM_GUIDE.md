# AGRO MIRAI: Team Guide for the Faculty Demo

Read this whole page once before you start. Every step is written so that you can follow it
without knowing anything technical. Copy the commands exactly as they are written.

**What you are going to show, in this order**

1. The backend running live on your laptop (it answers real GET and POST requests).
2. Live data coming in: weather, soil, and satellite (Google Earth Engine).
3. The three trained models: crop recommendation, irrigation advice, and the disease CNN that reads a leaf photo.
4. The previous real data stored in the cloud database (Supabase).
5. The three training notebooks, opened in Google Colab.
6. The landing page, already deployed on Vercel.

Total time to show everything: about 25 to 30 minutes. Setting up on your laptop the first
time takes 15 to 25 minutes, so do that before the faculty joins.

---

## PART 1. One-time installation (do this during the Google Meet with Ritesh)

You need a Windows laptop with internet. Nothing else has been installed yet, so we install
two programs: **Python 3.12** and **Visual Studio Code**.

### Step 1.1. Install Python 3.12

1. Press the Windows key, type `PowerShell`, and open **Windows PowerShell**.
2. Copy and paste this line, then press Enter:

   ```
   winget install Python.Python.3.12
   ```
3. If Windows asks whether to accept the source agreements, type `Y` and press Enter.
4. Wait until it says `Successfully installed`.
5. **Close PowerShell completely and open it again.** (This is important, otherwise Windows does not see Python yet.)
6. Check that it worked. Paste this and press Enter:

   ```
   py -3.12 --version
   ```
   You must see: `Python 3.12.x` (for example `Python 3.12.10`).

If `winget` is not found: go to https://www.python.org/downloads/windows/ , download
"Python 3.12" (Windows installer 64-bit), run it, and **tick the box "Add python.exe to PATH"**
on the first screen before you click Install Now.

### Step 1.2. Install Visual Studio Code

1. In PowerShell paste:

   ```
   winget install Microsoft.VisualStudioCode
   ```
2. Wait for `Successfully installed`. (Or download it from https://code.visualstudio.com )

### Step 1.3. Get the project onto your laptop

1. Ritesh sends you a file called `AGRO_MIRAI_DEMO.zip`. Download it.
2. Move it to a simple place such as `C:\` or the Desktop. **Do not** put it inside a folder that
   is synced by OneDrive if you can avoid it, and avoid very long folder names.
3. Right click the zip file, choose **Extract All...**, and press **Extract**.
4. You now have a folder called `AGRO_MIRAI_DEMO`. Open it. You should see files such as
   `app.py`, `setup.bat`, `run.bat`, `TEAM_GUIDE.md` and folders such as `src` and `models`.

> If you see **two** folders with the same name inside each other (`AGRO_MIRAI_DEMO\AGRO_MIRAI_DEMO`),
> open the inner one. The right folder is the one that directly contains `app.py`.

### Step 1.4. Open the project in VS Code

1. Open **Visual Studio Code**.
2. Click **File** then **Open Folder...**
3. Select the `AGRO_MIRAI_DEMO` folder (the one that contains `app.py`) and click **Select Folder**.
4. If VS Code asks "Do you trust the authors of the files in this folder?" click **Yes, I trust the authors**.
5. Open a terminal inside VS Code: click **Terminal** in the top menu then **New Terminal**.
   A panel opens at the bottom. It must show a line ending with `AGRO_MIRAI_DEMO>`.
   This bottom panel is called **the terminal**. All commands in this guide are typed there.

### Step 1.5. Run the one-time setup

In the terminal type this and press Enter:

```
.\setup.bat
```

What happens (this is normal, do not close anything):

- It creates a private Python environment in a folder called `.venv`.
- It downloads and installs the libraries (about 1.5 GB in total, the biggest one is PyTorch). **This takes 10 to 20 minutes.** Text scrolls a lot.
- At the end it builds the demo database: it **reads** the previous data from the cloud database (Supabase), then creates three synthetic demo fields and pulls **live** weather, soil and satellite data for them. Each field takes about 10 to 30 seconds.
- The last line says `Setup finished. Start the server with:  run.bat`

You only do this once per laptop. If it stops with a red error, see **Part 8 (Troubleshooting)**.

---

## PART 2. Starting the backend (do this before the faculty joins)

### Step 2.1. Start the server (Terminal 1)

In the terminal type:

```
.\run.bat
```

It first prints `Warming up the models, about 30 seconds ...`. **Wait for this line:**

```
READY. AGRO MIRAI demo backend on http://localhost:5000  (Ctrl+C to stop)
 * Running on http://127.0.0.1:5000
```

(A warning line saying "This is a development server" is normal, ignore it. PowerShell may show it in red, that is also normal.)
**Leave this terminal alone.** It is now the running backend. Do not press anything in it.

### Step 2.2. Open a second terminal for commands (Terminal 2)

In VS Code, click the **+** icon at the top right of the terminal panel (or press Ctrl+Shift+`).
A second terminal opens. **All demo commands below are typed in this second terminal.**

Quick test, type:

```
.\.venv\Scripts\python try_it.py health
```

You must see `HTTP 200` and `{"status": "ok"}`. If you see "Cannot reach the server", the server in
Terminal 1 is not running yet.

**How to read every command in this guide:** `.\.venv\Scripts\python try_it.py <something>` sends a
real web request to the backend and prints exactly what was sent (`>>> GET http://...`) and what came back
(`<<< HTTP 200` followed by the JSON answer). `GET` means "give me data", `POST` means "here is new data, save it".

To see all commands any time:

```
.\.venv\Scripts\python try_it.py help
```

---

## PART 3. The live demo, step by step

Each step has: **the command**, **what you will see**, and **what to tell the faculty**.

### Step 3.1. Show the project structure (2 minutes)

In VS Code's left panel (Explorer), click the folders and point at:

| Folder or file | What to say |
|---|---|
| `app.py` | The whole backend API in one small file. Every endpoint (GET and POST) is here. |
| `src\agro_mirai\acquisition` | Code that fetches **live** data: weather (Open-Meteo), soil (SoilGrids), satellite NDVI (Google Earth Engine). |
| `src\agro_mirai\processing` | Turns raw readings into the numbers the models need (7, 14 and 30 day weather summaries, soil, NDVI). |
| `src\agro_mirai\models` | The three models and the logic that explains their answers. |
| `models\` | The trained model files: `crop_rf.joblib`, `irrigation_rf.joblib`, `disease_cnn_mobilenetv2.pt`. |
| `src\agro_mirai\persistence` | Saving and loading data (local SQLite database for the demo, Supabase in production). |
| `notebooks\` | The three Google Colab notebooks that show how each model was trained. |
| `data\raw\` | The two training CSV files. |

### Step 3.2. GET requests: health, farmer, fields (3 minutes)

```
.\.venv\Scripts\python try_it.py health
.\.venv\Scripts\python try_it.py farmer
.\.venv\Scripts\python try_it.py fields
```

- `health` shows the server is alive (`{"status": "ok"}`).
- `farmer` shows the farmer profile. It is the real farmer stored in the cloud database.
- `fields` lists 4 fields: the real one ("North Cotton Plot", cotton, Ballari district) and three that start with `SYNTHETIC` (fields we created for the demo).
  It also prints a numbered list at the bottom (1 is the real field). **Those numbers (1, 2, 3, 4) are used in the next commands.**

Say: "Every farmer has fields. The API needs a secret key in a header, so nobody else can read this data."

### Step 3.3. Show the previous real data from the cloud database (2 minutes)

```
.\.venv\Scripts\python supabase_read.py
```

You will see the real production data: the farmer, the field, how many weather rows, soil samples, satellite
readings, advisories and feedback entries are stored, and the latest advisory.

Say: "This is our real cloud database (Supabase). This script only reads, it cannot change anything.
For the live demo we work on a local copy, so nothing we do here can damage production data."

### Step 3.4. POST request: create a field and pull LIVE data (2 minutes)

```
.\.venv\Scripts\python try_it.py newfield
```

This is a **POST**. It creates a new field ("Live Demo Plot" near Ballari) and immediately fetches live data.
The reply ends with a `live_data` block (the three sources can appear in any order) like:

```
"live_data": {
  "weather": {"ok": true, "seconds": 1.3},
  "soil":    {"ok": true, "seconds": 3.5},
  "ndvi":    {"ok": true, "seconds": 10.2}
}
```

`ok: true` for all three means real data was fetched from the internet just now.

Say: "The moment a farmer adds a field, the system fetches today's weather, the soil properties at that
exact GPS point, and the latest Sentinel-2 satellite reading from Google Earth Engine."

Now look at exactly what was fetched. The new field is the last one in the list (number 5):

```
.\.venv\Scripts\python try_it.py fields
.\.venv\Scripts\python try_it.py live 5
```

The `live` reply shows:
- `latest_weather`: temperature, humidity, rainfall with `"source": "open-meteo"`.
- `latest_soil`: the soil record with `"source": "soilgrids"`. The SoilGrids service often answers with empty chemistry values for a point.
  When that happens the system safely fills pH and nutrients with typical values for the field's soil type, and says so:
  look for `"soil_chemistry_source": "soil_type_fallback"` in `model_features`. Say this openly, it is our built-in fallback.
- `latest_ndvi`: the satellite greenness value. `"source": "gee_live"` means it came live from Google Earth Engine.
  If it says `"cache"`, Google Earth Engine was slow or unreachable and the system safely used its stored value (this is our built-in fallback, say so).
- `model_features`: the final numbers the models receive.

To fetch fresh data again at any time (a POST):

```
.\.venv\Scripts\python try_it.py refresh 5
```

### Step 3.5. Model 1: crop recommendation (2 minutes)

```
.\.venv\Scripts\python try_it.py crop 1
```

You see the recommended crop, a confidence value (about 0.35 to 0.4, it is spread over 22 crops), the alternatives, and `"out_of_region": true` with a `regional_alternative` when the crop is not normally grown in Ballari district.
(For the real cotton field the model suggests a crop such as muskmelon or watermelon. That is expected from a general dataset and is exactly why the regional check exists. Do not hide it, explain it.)

Say: "A Random Forest trained on 2,200 soil and weather records for 22 crops, 99.5% accuracy on held-out data.
It takes soil nitrogen, phosphorus, potassium, pH, temperature, humidity and rainfall, which are all filled in automatically from live data.
Because the training data is a general dataset, we added a regional check that warns when a crop is not grown in this district."

### Step 3.6. Model 2: irrigation advice (2 minutes)

```
.\.venv\Scripts\python try_it.py irrigation 1
```

You see the urgency (low, moderate, high), the recommended water depth in millimetres, and a window of days.

Say: "A Random Forest predicts how urgent irrigation is. The number of millimetres is not guessed: we compute it with
the FAO-56 water balance, that is reference evapotranspiration from temperature and location, times a crop coefficient for
the crop and its growth stage, minus the rain that fell."

### Step 3.7. Disease risk from weather, and the combined advisory (2 minutes)

```
.\.venv\Scripts\python try_it.py disease 1
.\.venv\Scripts\python try_it.py advisory 1
```

- `disease` is the weather-based disease risk score (humidity, rain, temperature and NDVI trend).
- `advisory` combines crop, irrigation and disease into one plain-language advisory with a severity. The newest advisory is first in the list.
  It can take 5 to 15 seconds the first time (the system computes SHAP explanations of why each model answered as it did).

Say: "The decision engine puts the three models together and explains, in plain words, which factors drove each answer."

### Step 3.8. Model 3: the CNN reads a leaf photo (5 minutes, the main highlight)

The folder `samples\` has six real leaf photos from the PlantVillage dataset. Run these one at a time:

```
.\.venv\Scripts\python try_it.py scan samples\tomato_late_blight.jpg 1
.\.venv\Scripts\python try_it.py scan samples\maize_common_rust.jpg 1
.\.venv\Scripts\python try_it.py scan samples\grape_black_rot.jpg 1
.\.venv\Scripts\python try_it.py scan samples\apple_healthy.jpg 1
.\.venv\Scripts\python try_it.py scan samples\maize_healthy.jpg 1
.\.venv\Scripts\python try_it.py scan samples\potato_early_blight.jpg 1
```

Each answer is a `POST` of the image. Look at:
- `disease`: what the CNN saw on the leaf (for example "Tomato: Late blight").
- `risk_level` and `confidence`.
- `top_predictions`: the model's top three guesses with probabilities.
- `"source": "cnn"` and `"analysed_by": "MobileNetV2 CNN trained on PlantVillage (38 classes)"`.

The answer **changes with the photo**. That is the proof that the network really analysed the image.

To use any other picture, put it in the `samples` folder (jpg or png) and use its name in the same command.
Optional honesty check, a photo that is **not** a leaf (a farmer portrait is included):

```
.\.venv\Scripts\python try_it.py scan samples\not_a_leaf_farmer_photo.jpg 1
```

The CNN still answers, but with a much lower confidence (about 0.5 instead of 0.99+), because it can only choose among the 38 classes it has learned. Say that honestly if asked.
Also try a file that is not an image at all (`.\.venv\Scripts\python try_it.py scan app.py 1`); the API refuses it with `HTTP 400 file is not a valid image`.

Note for the faculty: the six sample photos come from the PlantVillage dataset, the same collection the network was trained on,
so the high confidence is expected. Real field photos are harder (see the questions in Part 6).

Say: "MobileNetV2, a small convolutional network, pre-trained on ImageNet and fine-tuned on about 54,000 PlantVillage leaf images
across 38 classes, 99.2% validation accuracy. The photo goes straight into the network inside the backend."

### Step 3.9. POST feedback and GET it back (2 minutes)

```
.\.venv\Scripts\python try_it.py feedback 1
.\.venv\Scripts\python try_it.py feedbacks
```

The first is a POST that rates the newest advisory (5 stars, helpful). The second is a GET that lists all saved feedback,
so the faculty can see the new entry.

Say: "Farmers rate each advisory. That feedback is stored, and it is what we use to improve the system over time."

### Step 3.10. Optional: open it in a normal web browser

While the server is running, open Chrome and go to `http://localhost:5000/` . You see the list of endpoints.
`http://localhost:5000/health` shows the health answer. (The data endpoints need the secret key header, which is why we use `try_it.py`.)

### Step 3.11. Stop the server

Click into Terminal 1 (the one running the server) and press `Ctrl+C`.

---

## PART 4. The three notebooks (Google Colab)

Ritesh also sends these three files (they are also in the `notebooks` folder of this project):

- `01_crop_recommendation.ipynb`
- `02_irrigation_advisory.ipynb`
- `03_disease_risk_detection.ipynb`

To open one:

1. Go to https://colab.research.google.com and sign in with any Google account.
2. Click **File** then **Upload notebook**, and choose the file.
3. Read the cells top to bottom, and click the play button on each code cell (or **Runtime > Run all**).

Notebooks 1 and 2 download the training data from Kaggle, which needs a Kaggle token. Do **one** of these two options:

- **Option A (recommended, nothing shows on screen):**
  1. In Colab click the **key icon** (Secrets) in the left bar.
  2. Click **Add new secret**. Name: `KAGGLE_API_TOKEN`. Value: paste the single line from the file `keys\kaggle_access_token.txt` in this project.
  3. Switch **Notebook access** on for that secret.
  4. Run the notebook. The cell titled "Get the real training data" will say `Using the KAGGLE_API_TOKEN Colab secret.`
- **Option B (no Kaggle at all):** skip the download cells and instead upload the CSV from this project's `data\raw` folder
  (`Crop_recommendation.csv` for notebook 1, `irrigation_prediction.csv` for notebook 2) into the Colab files panel, inside a folder named `data/raw`.

Notebook 3 does not need Kaggle. It explains the disease risk score and documents the CNN
(the CNN training itself needed a GPU on Colab and took a few minutes; the trained result is the file `models\disease_cnn_mobilenetv2.pt`).

What to say for each notebook is in **Part 6**.

---

## PART 5. The landing page

Open https://agromirai.vercel.app in Chrome. It is hosted on Vercel. Scroll through it: it explains the problem, the
features (crop recommendation, irrigation, disease detection, voice in four languages), and how the product works.

---

## PART 6. How to explain the project to the faculty (script you can follow)

### The problem in one sentence
Small farmers in Karnataka decide what to grow, when to irrigate and how to react to disease using guesswork; AGRO MIRAI turns
free public data (weather, soil, satellite) and three trained AI models into one plain-language advisory for each field.

### The flow in one line (say it while pointing at `src\agro_mirai`)
`field location -> live weather + soil + satellite data -> features -> 3 models -> one advisory with reasons -> farmer feedback`

### The three models

| Model | Type | Trained on | Result | Where |
|---|---|---|---|---|
| Crop recommendation | Random Forest classifier, 22 crops | Kaggle crop recommendation, 2,200 rows | 99.55% accuracy | `models\crop_rf.joblib`, notebook 1 |
| Irrigation advice | Random Forest classifier for urgency, plus FAO-56 water balance for millimetres | Kaggle irrigation water requirement, 10,000 rows | 72.4% accuracy, macro-F1 0.58 (the High class is rare) | `models\irrigation_rf.joblib`, notebook 2 |
| Disease from a leaf photo | CNN, MobileNetV2 transfer learning, 38 classes | PlantVillage, about 54,300 images | 99.24% validation accuracy | `models\disease_cnn_mobilenetv2.pt`, notebook 3 |

Dataset links and training details are in `DATASETS.md`.

### Notebook talking points
- **Notebook 1:** load the Kaggle CSV, look at the 22 balanced crops, train the Random Forest, show accuracy, then use SHAP to show *why* it recommends a crop.
- **Notebook 2:** show the Random Forest for urgency, then the FAO-56 formula for millimetres (evapotranspiration times crop coefficient minus rainfall).
- **Notebook 3:** show the weather-based disease score (weights: humidity 40%, rain 25%, temperature 15%, NDVI trend 20%) and explain the CNN.

### Questions the faculty may ask, and honest answers

- **Is the data live or fixed?** Weather, soil and satellite values are fetched live when a field is created or refreshed (you saw the `live_data` block with real timings).
- **What if Google Earth Engine is down?** The system falls back to its stored NDVI value and says so in the `source` field. It never crashes.
- **Is 99% on the CNN realistic on a farm?** No, be honest: 99.24% is on PlantVillage photos taken in lab conditions. Real field photos are harder; the next step is training on PlantDoc (real-world photos, link in `DATASETS.md`).
- **Why is the irrigation accuracy only 72%?** The dataset is imbalanced (only 336 High examples out of 10,000). The millimetre amount is not learned but computed from the FAO-56 standard, which is more trustworthy.
- **Why does it recommend muskmelon or watermelon for a Ballari cotton field?** The crop model is trained on a general dataset. That is exactly why we added the regional check, which prints a caution when a crop is not normally grown in the district.
- **Where is the data stored?** In production: Supabase (PostgreSQL in the cloud). For this demo: a local SQLite file, so nothing here can affect the real database.
- **What is not in this demo?** The mobile app, the voice assistant (Kannada, Hindi, Telugu, English), and the admin dashboard. They exist but are not part of today's presentation.
- **Is the API secure?** Every data endpoint needs a secret key in the request header. Keys live in the `.env` file, not in the code.

---

## PART 7. Command cheat sheet (Terminal 2)

| What | Command |
|---|---|
| All commands | `.\.venv\Scripts\python try_it.py help` |
| Server alive (GET) | `.\.venv\Scripts\python try_it.py health` |
| Farmer (GET) | `.\.venv\Scripts\python try_it.py farmer` |
| Fields, numbered (GET) | `.\.venv\Scripts\python try_it.py fields` |
| Real cloud data (read only) | `.\.venv\Scripts\python supabase_read.py` |
| New field + live data (POST) | `.\.venv\Scripts\python try_it.py newfield` |
| Live data of field N (GET) | `.\.venv\Scripts\python try_it.py live N` |
| Fetch fresh live data (POST) | `.\.venv\Scripts\python try_it.py refresh N` |
| Crop model (GET) | `.\.venv\Scripts\python try_it.py crop N` |
| Irrigation model (GET) | `.\.venv\Scripts\python try_it.py irrigation N` |
| Weather disease risk (GET) | `.\.venv\Scripts\python try_it.py disease N` |
| CNN reads a photo (POST) | `.\.venv\Scripts\python try_it.py scan samples\tomato_late_blight.jpg N` |
| Combined advisory (GET) | `.\.venv\Scripts\python try_it.py advisory N` |
| Send feedback (POST) | `.\.venv\Scripts\python try_it.py feedback N` |
| List feedback (GET) | `.\.venv\Scripts\python try_it.py feedbacks` |
| Start the server (Terminal 1) | `.\run.bat` |
| Rebuild the demo database (first stop the server with Ctrl+C in Terminal 1, and start it again afterwards with `.\run.bat`) | `.\.venv\Scripts\python seed_demo_data.py` |

`N` is the field number from `try_it.py fields` (field 1 is the real field). If you leave `N` out, field 1 is used.

---

## PART 8. Troubleshooting

| What you see | What to do |
|---|---|
| `py` or `python` is not recognised | Close and reopen PowerShell / VS Code after installing Python. If still failing, reinstall Python and tick "Add python.exe to PATH". |
| `.\setup.bat` says `Python 3.12 was not found` | Run `winget install Python.Python.3.12`, close and reopen VS Code, run setup again. |
| Setup fails while downloading (a red error about a connection or timeout) | Check the internet and simply run `.\setup.bat` again. It resumes. |
| Setup finishes but says it could not read Supabase | Check the internet, make sure the server is stopped (Ctrl+C in Terminal 1), then run `.\.venv\Scripts\python seed_demo_data.py` again. The demo still works with a local farmer only. |
| `Cannot reach the server` | Terminal 1 is not running the server. Type `.\run.bat` there and wait for `Running on http://127.0.0.1:5000`. |
| `Address already in use` / port 5000 busy | Another program uses port 5000. Close it, or restart the laptop. |
| `HTTP 401` | The `.env` file is missing or was edited. Get a fresh copy from Ritesh. |
| `HTTP 422 NO_WEATHER_DATA` | Run `.\.venv\Scripts\python try_it.py refresh N` for that field, then try again. |
| Live NDVI shows `"source": "cache"` | Google Earth Engine was slow. This is the safe built-in fallback and is normal. Run `refresh N` again to try live once more. |
| `advisory` takes about 5 seconds | Normal. It runs three models and computes SHAP explanations. |
| You see the word `Traceback` in Terminal 1 | Copy the last 10 lines and send them to Ritesh. |
| PowerShell says scripts are disabled | We do not use activation scripts. Keep using `.\.venv\Scripts\python ...` exactly as written. |
| Everything is broken | Close VS Code, delete the `.venv` and `demo.db` files, open the folder again, run `.\setup.bat` again. |

---

## PART 9. Important: keys and sharing

This folder contains **real** secret keys (`.env` and the `keys` folder). Keep the zip inside the team,
do not upload it to GitHub, Drive links open to everyone, or any public place, and delete it after the presentation.
Ritesh will rotate (replace) the keys after the demo.
