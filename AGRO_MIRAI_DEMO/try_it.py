"""Calls the demo backend and prints each request and its answer.

The server must be running first (run.bat, in another terminal).

Usage:   python try_it.py <command> [argument]

  health                 GET  /health
  farmer                 GET  /farmers/me
  fields                 GET  /fields                      (numbered list)
  newfield               POST /fields                      (creates a field, pulls live data)
  live [n]               GET  /fields/<n>/live-data        (weather, soil, satellite + model inputs)
  refresh [n]            POST /fields/<n>/refresh-data     (fetch fresh live data again)
  crop [n]               GET  /fields/<n>/recommendation   (model 1: crop recommendation)
  irrigation [n]         GET  /fields/<n>/irrigation       (model 2: irrigation advice)
  disease [n]            GET  /fields/<n>/disease-risk     (weather based disease risk)
  scan <image> [n]       POST /fields/<n>/disease-risk/image  (model 3: CNN reads the leaf photo)
  advisory [n]           GET  /fields/<n>/advisories       (all models combined into one advisory)
  feedback [n]           POST /feedback                    (rates the newest advisory of field n)
  feedbacks              GET  /feedback

[n] is the field number from "fields" (default 1).
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
BASE = "http://127.0.0.1:5000"
HEADERS = {"Authorization": "Bearer " + os.environ.get("API_KEY", "")}


def call(method, path, **kwargs):
    print(f"\n>>> {method} {BASE}{path}")
    try:
        resp = requests.request(method, BASE + path, headers=HEADERS, timeout=180, **kwargs)
    except requests.ConnectionError:
        sys.exit("Cannot reach the server. Start it first with run.bat (in another terminal).")
    print(f"<<< HTTP {resp.status_code}")
    try:
        body = resp.json()
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return body
    except ValueError:
        print(resp.text)


def oldest_first(items):
    """Stable numbering for the demo: the real field is 1, new fields come last."""
    return sorted(items, key=lambda f: f["created_at"])


def field_id(n):
    items = oldest_first(requests.get(BASE + "/fields", headers=HEADERS, timeout=30).json()["items"])
    if not items:
        sys.exit("No fields yet. Run seed_demo_data.py")
    n = max(1, min(int(n or 1), len(items)))
    print(f"(using field {n}: {items[n - 1]['name']})")
    return items[n - 1]["id"]


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, arg = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)

    if cmd == "health":
        call("GET", "/health")
    elif cmd == "farmer":
        call("GET", "/farmers/me")
    elif cmd == "fields":
        body = call("GET", "/fields")
        print("\nNumbered list:")
        for i, f in enumerate(oldest_first(body["items"]), 1):
            print(f"  {i}. {f['name']}  ({f['current_crop']}, {f['area_ha']} ha)")
    elif cmd == "newfield":
        call(
            "POST",
            "/fields",
            json={
                "name": "Live Demo Plot",
                "latitude": 15.1394,
                "longitude": 76.9214,
                "area_ha": 2.0,
                "soil_type": "black",
                "current_crop": "cotton",
                "sown_on": "2026-07-15",
            },
        )
    elif cmd == "live":
        call("GET", f"/fields/{field_id(arg)}/live-data")
    elif cmd == "refresh":
        call("POST", f"/fields/{field_id(arg)}/refresh-data")
    elif cmd == "crop":
        call("GET", f"/fields/{field_id(arg)}/recommendation")
    elif cmd == "irrigation":
        call("GET", f"/fields/{field_id(arg)}/irrigation")
    elif cmd == "disease":
        call("GET", f"/fields/{field_id(arg)}/disease-risk")
    elif cmd == "scan":
        if not arg:
            sys.exit("Usage: python try_it.py scan <image file> [field number]")
        image = Path(arg)
        if not image.exists():
            sys.exit(f"Image not found: {image}")
        fid = field_id(sys.argv[3] if len(sys.argv) > 3 else None)
        with open(image, "rb") as fh:
            call("POST", f"/fields/{fid}/disease-risk/image", files={"image": (image.name, fh)})
    elif cmd == "advisory":
        call("GET", f"/fields/{field_id(arg)}/advisories")
    elif cmd == "feedback":
        fid = field_id(arg)
        items = requests.get(f"{BASE}/fields/{fid}/advisories", headers=HEADERS, timeout=180).json()["items"]
        call(
            "POST",
            "/feedback",
            json={"advisory_id": items[0]["id"], "rating": 5, "helpful": True, "comment": "Clear and useful"},
        )
    elif cmd == "feedbacks":
        call("GET", "/feedback")
    else:
        print(__doc__)


main()
