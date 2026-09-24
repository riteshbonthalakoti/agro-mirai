"""Builds src/agro_mirai/models/data/ecocrop_crops.json from the FAO EcoCrop
database (CC0). Usage:

    curl -L https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv -o EcoCrop_DB.csv
    python tools/build_ecocrop_table.py EcoCrop_DB.csv

Only the 22 crops from specs/core/enums.md are kept, and only the columns
the scorer uses (temperature, annual rainfall, pH, soil texture).
"""
import json
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "src/agro_mirai/models/data/ecocrop_crops.json"

# our crop label -> scientific name used in EcoCrop
CROPS = {
    "apple": "Malus domestica", "banana": "Musa acuminata", "blackgram": "Vigna mungo",
    "chickpea": "Cicer arietinum", "coconut": "Cocos nucifera", "coffee": "Coffea arabica",
    "cotton": "Gossypium hirsutum", "grapes": "Vitis vinifera", "jute": "Corchorus olitorius",
    "kidneybeans": "Phaseolus vulgaris", "lentil": "Lens culinaris", "maize": "Zea mays",
    "mango": "Mangifera indica", "mothbeans": "Vigna aconitifolia", "mungbean": "Vigna radiata",
    "muskmelon": "Cucumis melo", "orange": "Citrus sinensis", "papaya": "Carica papaya",
    "pigeonpeas": "Cajanus cajan", "pomegranate": "Punica granatum", "rice": "Oryza sativa",
    "watermelon": "Citrullus lanatus",
}
COLS = ["TOPMN", "TOPMX", "TMIN", "TMAX", "ROPMN", "ROPMX", "RMIN", "RMAX", "PHOPMN", "PHOPMX", "PHMIN", "PHMAX", "TEXT"]


def main(csv_path):
    df = pd.read_csv(csv_path, encoding="latin1", low_memory=False)
    out = {}
    for crop, sci in CROPS.items():
        rows = df[df["ScientificName"].astype(str).str.startswith(sci)]
        if rows.empty:
            genus = sci.split()[0]
            rows = df[df["ScientificName"].astype(str).str.startswith(genus)]
        if rows.empty:
            raise SystemExit(f"no EcoCrop row for {crop} ({sci})")
        r = rows.iloc[0]
        entry = {"scientific_name": str(r["ScientificName"])}
        for c in COLS:
            v = r[c]
            entry[c.lower()] = None if pd.isna(v) else (str(v) if c == "TEXT" else float(v))
        out[crop] = entry
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", OUT, len(out), "crops")


if __name__ == "__main__":
    main(sys.argv[1])
