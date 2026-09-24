"""Does the PlantDoc fine-tune still recognise PlantVillage lab photos?

Run on the same Colab session as train_disease_cnn_plantdoc.py (needs
/content/in/disease_cnn_mobilenetv2.pt = old model and
/content/out/disease_cnn_plantdoc.pt = new model). Downloads a fixed sample per
class from the color test split of the public Hugging Face copy of PlantVillage
(mohanty/PlantVillage, the original authors' repo; tensorflow-datasets'
download link is dead) and scores both models on it. The old model was trained on these images, so its number is a ceiling; the
question is only how much the new one lost.
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

subprocess.run([sys.executable, "-m", "pip", "-q", "install", "huggingface_hub"], check=False)

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from huggingface_hub import hf_hub_download
from PIL import Image
from torchvision import models, transforms

dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
names = json.loads(Path("/content/in/disease_cnn_class_names.json").read_text())
norm = lambda s: re.sub(r"[\s_]+", " ", s.lower()).strip()  # noqa: E731
idx = {norm(n): i for i, n in enumerate(names)}


def load(path):
    m = models.mobilenet_v2(weights=None)
    m.classifier[1] = nn.Linear(m.last_channel, len(names))
    m.load_state_dict(torch.load(path, map_location="cpu"))
    return m.to(dev).eval()


old, new = load("/content/in/disease_cnn_mobilenetv2.pt"), load("/content/out/disease_cnn_plantdoc.pt")
tf = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

REPO = "mohanty/PlantVillage"
listing = Path(hf_hub_download(REPO, "splits/color_test.txt", repo_type="dataset")).read_text().splitlines()
by_class = defaultdict(list)
for line in listing:
    parts = line.strip().split("/")  # raw/color/<Class>/<file>
    if len(parts) == 4 and norm(parts[2]) in idx:
        by_class[idx[norm(parts[2])]].append(line.strip())
PER = 40
import io
import zipfile

zpath = hf_hub_download(REPO, "data.zip", repo_type="dataset")
zf = zipfile.ZipFile(zpath)
zip_names = set(zf.namelist())
print("zip entries:", len(zip_names), "e.g.", sorted(zip_names)[:2], flush=True)
by_suffix = {}
for n in zip_names:
    if "/color/" in n and not n.endswith("/"):
        by_suffix[n.split("/color/", 1)[1]] = n  # "<Class>/<file>"
xs, ys = [], []
missing = 0
for ci, files in sorted(by_class.items()):
    for f in sorted(files)[:PER]:
        key = f.split("/color/", 1)[1]
        zn = f if f in zip_names else by_suffix.get(key)
        if zn is None:
            missing += 1
            continue
        xs.append(tf(Image.open(io.BytesIO(zf.read(zn))).convert("RGB")))
        ys.append(ci)
print("missing in zip:", missing, flush=True)
X, Y = torch.stack(xs), np.array(ys)
print("PlantVillage sample:", len(Y), flush=True)


@torch.no_grad()
def acc(model):
    p = []
    for i in range(0, len(X), 128):
        p.append(F.softmax(model(X[i:i + 128].to(dev)), 1).cpu())
    probs = torch.cat(p).numpy()
    pred = probs.argmax(1)
    return {"top1": float((pred == Y).mean()), "mean_confidence": float(probs.max(1).mean())}


res = {"n": int(len(Y)), "old_model": acc(old), "new_model": acc(new)}
print("FORGETTING", json.dumps(res, indent=1), flush=True)
Path("/content/out/forgetting.json").write_text(json.dumps(res, indent=2))
