"""Fine-tunes the Module 20 disease CNN on PlantDoc (real, non-lab photos).

Run on a Colab GPU session, driven from this machine with the colab CLI:

    wsl colab new --gpu T4 -s plantdoc
    wsl colab upload -s plantdoc models/disease_cnn_mobilenetv2.pt /content/in/disease_cnn_mobilenetv2.pt
    wsl colab upload -s plantdoc models/disease_cnn_class_names.json /content/in/disease_cnn_class_names.json
    wsl colab exec -s plantdoc -f tools/train_disease_cnn_plantdoc.py --timeout 5400
    wsl colab download -s plantdoc /content/out/<file> <local path>

Why: the PlantVillage-only model scores ~99% on PlantVillage but PlantVillage
is single leaves on plain backgrounds. PlantDoc (Singh et al., CoDS-COMAD 2020,
CC BY 4.0, github.com/pratikkayal/PlantDoc-Dataset, "Cropped-PlantDoc") is
internet photos with real backgrounds, closer to what a farmer's phone takes.

What it does: measures the OLD model on PlantDoc's test split (the honest
field number), fine-tunes on PlantDoc train + a PlantVillage replay sample
(so lab-image classes are not forgotten) with a distillation term from the old
model and label smoothing, picks the epoch on a PlantDoc validation slice (not
the test split), then reports old vs new on the untouched PlantDoc test split
and on a PlantVillage sample, plus calibration (ECE) and how accurate the
model is when it is confident (the "not sure" threshold in disease_cnn_labels).

Outputs in /content/out: disease_cnn_plantdoc.pt, disease_cnn_plantdoc.onnx,
disease_cnn_plantdoc_eval.json (and class names json is unchanged: 38 classes).
"""
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

subprocess.run([sys.executable, "-m", "pip", "-q", "install", "onnx", "onnxruntime", "onnxscript"], check=False)

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("device:", dev, flush=True)

IN = Path("/content/in")
OUT = Path("/content/out")
OUT.mkdir(parents=True, exist_ok=True)
names = json.loads((IN / "disease_cnn_class_names.json").read_text())
if isinstance(names, dict):  # {"0": "Apple___..."} or {"classes": [...]}
    names = names.get("classes") or [names[str(i)] for i in range(len(names))]
NC = len(names)
idx_of = {n: i for i, n in enumerate(names)}
print("classes:", NC, flush=True)

# ---------------------------------------------------------------- PlantDoc
PD = Path("/content/plantdoc")
if not PD.exists():
    subprocess.run(["git", "clone", "--depth", "1", "https://github.com/pratikkayal/PlantDoc-Dataset", str(PD)], check=True)


def norm(s):
    return re.sub(r"[\s_]+", " ", s.lower()).strip()


# PlantDoc folder -> PlantVillage class name (only classes that exist in both)
PD_TO_PV = {
    "apple scab leaf": "Apple___Apple_scab", "apple leaf": "Apple___healthy",
    "apple rust leaf": "Apple___Cedar_apple_rust",
    "bell pepper leaf": "Pepper,_bell___healthy", "bell pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "blueberry leaf": "Blueberry___healthy", "cherry leaf": "Cherry_(including_sour)___healthy",
    "corn gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight", "corn rust leaf": "Corn_(maize)___Common_rust_",
    "peach leaf": "Peach___healthy", "potato leaf early blight": "Potato___Early_blight",
    "potato leaf late blight": "Potato___Late_blight", "raspberry leaf": "Raspberry___healthy",
    "soyabean leaf": "Soybean___healthy", "squash powdery mildew leaf": "Squash___Powdery_mildew",
    "strawberry leaf": "Strawberry___healthy",
    "tomato early blight leaf": "Tomato___Early_blight", "tomato septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "tomato leaf": "Tomato___healthy", "tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "tomato leaf late blight": "Tomato___Late_blight", "tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "tomato mold leaf": "Tomato___Leaf_Mold",
    "tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
    "grape leaf": "Grape___healthy", "grape leaf black rot": "Grape___Black_rot",
}
# our class names may differ slightly in spacing/underscores: match on a normalised key
pv_key = {norm(n): n for n in names}


def collect(split):
    items, unmapped = [], Counter()
    for d in sorted((PD / split).iterdir()):
        if not d.is_dir():
            continue
        target = PD_TO_PV.get(norm(d.name))
        target = pv_key.get(norm(target)) if target else None
        files = [p for p in d.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
        if target is None:
            unmapped[d.name] += len(files)
            continue
        items += [(str(p), idx_of[target]) for p in files]
    return items, unmapped


pd_train_all, un1 = collect("train")
pd_test, un2 = collect("test")
print("PlantDoc train imgs:", len(pd_train_all), "test imgs:", len(pd_test), flush=True)
print("UNMAPPED PlantDoc folders (skipped):", dict(un1 + un2), flush=True)
random.Random(SEED).shuffle(pd_train_all)
n_val = max(1, int(0.10 * len(pd_train_all)))
pd_val, pd_train = pd_train_all[:n_val], pd_train_all[n_val:]

# --------------------------------------------------- PlantVillage replay (tfds)
pv_replay, pv_hold = [], []
try:
    import tensorflow_datasets as tfds

    ds, info = tfds.load("plant_village", split="train", with_info=True, as_supervised=True)
    tf_names = info.features["label"].names
    tf_to_idx = {}
    for i, n in enumerate(tf_names):
        k = pv_key.get(norm(n))
        if k is not None:
            tf_to_idx[i] = idx_of[k]
    print("tfds classes mapped:", len(tf_to_idx), "of", len(tf_names), flush=True)
    per_class = defaultdict(int)
    PV_DIR = Path("/content/pv")
    PV_DIR.mkdir(exist_ok=True)
    N_REPLAY, N_HOLD = 60, 25
    for img, lab in tfds.as_numpy(ds):
        ci = tf_to_idx.get(int(lab))
        if ci is None:
            continue
        c = per_class[ci]
        if c >= N_REPLAY + N_HOLD:
            if all(v >= N_REPLAY + N_HOLD for v in per_class.values()) and len(per_class) == len(tf_to_idx):
                break
            continue
        per_class[ci] += 1
        p = PV_DIR / f"{ci}_{c}.jpg"
        Image.fromarray(img).save(p, quality=92)
        (pv_replay if c < N_REPLAY else pv_hold).append((str(p), ci))
except Exception as e:  # noqa: BLE001
    print("!! PlantVillage replay unavailable, training with distillation only:", repr(e), flush=True)
print("PV replay:", len(pv_replay), "PV holdout:", len(pv_hold), flush=True)

# ------------------------------------------------------------------- data
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
train_tf = transforms.Compose([
    transforms.RandomResizedCrop(224, scale=(0.45, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(25),
    transforms.ColorJitter(0.4, 0.4, 0.4, 0.05),
    transforms.RandomApply([transforms.GaussianBlur(5, (0.1, 1.5))], p=0.3),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
    transforms.RandomErasing(p=0.25, scale=(0.02, 0.12)),
])
eval_tf = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize(MEAN, STD)])


class DS(torch.utils.data.Dataset):
    def __init__(self, items, tf):
        self.items, self.tf = items, tf

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        p, y = self.items[i]
        return self.tf(Image.open(p).convert("RGB")), y


REPEAT_PD = 3
train_items = pd_train * REPEAT_PD + pv_replay
train_dl = torch.utils.data.DataLoader(DS(train_items, train_tf), batch_size=32, shuffle=True, num_workers=2, drop_last=True)
mk = lambda items: torch.utils.data.DataLoader(DS(items, eval_tf), batch_size=64, shuffle=False, num_workers=2)  # noqa: E731
pd_val_dl, pd_test_dl = mk(pd_val), mk(pd_test)
pv_hold_dl = mk(pv_hold) if pv_hold else None


def build(path=None):
    m = models.mobilenet_v2(weights=None)
    m.classifier[1] = nn.Linear(m.last_channel, NC)
    if path:
        sd = torch.load(path, map_location="cpu")
        m.load_state_dict(sd.get("state_dict", sd) if isinstance(sd, dict) else sd)
    return m.to(dev)


@torch.no_grad()
def predict(model, dl):
    model.eval()
    probs, ys = [], []
    for x, y in dl:
        probs.append(F.softmax(model(x.to(dev)), 1).cpu())
        ys.append(y)
    return torch.cat(probs).numpy(), torch.cat(ys).numpy()


def metrics(probs, ys, unsure_below=0.55):
    pred = probs.argmax(1)
    conf = probs.max(1)
    acc = float((pred == ys).mean())
    # macro-F1 over classes that appear in ys
    f1s = []
    for c in np.unique(ys):
        tp = ((pred == c) & (ys == c)).sum()
        fp = ((pred == c) & (ys != c)).sum()
        fn = ((pred != c) & (ys == c)).sum()
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    # expected calibration error, 10 bins
    ece, bins = 0.0, np.linspace(0, 1, 11)
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs((pred[m] == ys[m]).mean() - conf[m].mean())
    sure = conf >= unsure_below
    return {
        "n": int(len(ys)), "top1": acc, "macro_f1": float(np.mean(f1s)), "ece": float(ece),
        "mean_confidence": float(conf.mean()),
        "share_answered_when_confident": float(sure.mean()),
        "accuracy_when_confident": float((pred[sure] == ys[sure]).mean()) if sure.any() else None,
        "top3": float(np.mean([ys[i] in np.argsort(-probs[i])[:3] for i in range(len(ys))])),
    }


# ---------------------------------------------------------------- baseline
teacher = build(IN / "disease_cnn_mobilenetv2.pt")
teacher.eval()
base = {"plantdoc_test": metrics(*predict(teacher, pd_test_dl))}
if pv_hold_dl:
    base["plantvillage_sample"] = metrics(*predict(teacher, pv_hold_dl))
print("BASELINE (old model):", json.dumps(base, indent=1), flush=True)

# ------------------------------------------------------------------ train
model = build(IN / "disease_cnn_mobilenetv2.pt")
for p in model.parameters():
    p.requires_grad = False
for blk in list(model.features)[-6:]:
    for p in blk.parameters():
        p.requires_grad = True
for p in model.classifier.parameters():
    p.requires_grad = True
params = [p for p in model.parameters() if p.requires_grad]
EPOCHS = 14
opt = torch.optim.AdamW(params, lr=3e-4, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-4, total_steps=EPOCHS * len(train_dl), pct_start=0.15)
KD_W, KD_T = 0.3, 2.0
best_acc, best_state, history = -1.0, None, []
t0 = time.time()
for ep in range(1, EPOCHS + 1):
    model.train()
    tot, n = 0.0, 0
    for x, y in train_dl:
        x, y = x.to(dev), y.to(dev)
        logits = model(x)
        loss = F.cross_entropy(logits, y, label_smoothing=0.1)
        with torch.no_grad():
            t_logits = teacher(x)
        loss = loss + KD_W * (KD_T ** 2) * F.kl_div(
            F.log_softmax(logits / KD_T, 1), F.softmax(t_logits / KD_T, 1), reduction="batchmean"
        )
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        tot += loss.item() * len(y)
        n += len(y)
    va = metrics(*predict(model, pd_val_dl))
    history.append({"epoch": ep, "train_loss": tot / n, "plantdoc_val_top1": va["top1"], "plantdoc_val_ece": va["ece"]})
    print(f"epoch {ep:2d} loss {tot / n:.3f} PD-val top1 {va['top1']:.3f} ece {va['ece']:.3f}  ({time.time() - t0:.0f}s)", flush=True)
    if va["top1"] > best_acc:
        best_acc = va["top1"]
        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

model.load_state_dict(best_state)
new = {"plantdoc_test": metrics(*predict(model, pd_test_dl))}
if pv_hold_dl:
    new["plantvillage_sample"] = metrics(*predict(model, pv_hold_dl))
print("NEW (fine-tuned):", json.dumps(new, indent=1), flush=True)

# ----------------------------------------------------------------- export
torch.save(model.state_dict(), OUT / "disease_cnn_plantdoc.pt")
model.eval().cpu()
dummy = torch.randn(1, 3, 224, 224)
onnx_path = OUT / "disease_cnn_plantdoc.onnx"
try:
    torch.onnx.export(model, dummy, str(onnx_path), input_names=["input"], output_names=["logits"], opset_version=17, dynamo=False)
except TypeError:
    torch.onnx.export(model, dummy, str(onnx_path), input_names=["input"], output_names=["logits"], opset_version=17)
import onnxruntime as ort

sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
with torch.no_grad():
    ref = model(dummy).numpy()
got = sess.run(None, {"input": dummy.numpy()})[0]
max_diff = float(np.abs(ref - got).max())
print("onnx max abs diff vs torch:", max_diff, " size MB:", round(onnx_path.stat().st_size / 1e6, 2), flush=True)

report = {
    "what": "MobileNetV2 disease CNN, PlantVillage-trained (old) vs fine-tuned on PlantDoc + PlantVillage replay (new)",
    "plantdoc": "Cropped-PlantDoc, Singh et al. 2020 (CoDS-COMAD), CC BY 4.0",
    "plantdoc_train_images": len(pd_train), "plantdoc_val_images": len(pd_val), "plantdoc_test_images": len(pd_test),
    "plantdoc_unmapped_folders_skipped": dict(un1 + un2),
    "plantvillage_replay_images": len(pv_replay), "plantvillage_sample_images": len(pv_hold),
    "epochs": EPOCHS, "best_epoch_chosen_on": "PlantDoc validation slice (10% of train), never the test split",
    "recipe": "unfreeze last 6 feature blocks, AdamW 3e-4 one-cycle, label smoothing 0.1, KD from old model (w=0.3, T=2), PlantDoc x3 + PV replay",
    "trained_at_utc": time.strftime("%Y-%m-%d", time.gmtime()),
    "baseline_old_model": base, "new_model": new,
    "onnx_max_abs_diff_vs_torch": max_diff, "onnx_size_mb": round(onnx_path.stat().st_size / 1e6, 2),
    "history": history,
    "caveats": [
        "PlantDoc is small (~2.5k images) and internet-scraped; its test split is the best available stand-in for phone photos, not real farmer photos from Karnataka.",
        "PV sample images are drawn from data the OLD model was trained on, so that column measures forgetting, not generalisation.",
    ],
}
(OUT / "disease_cnn_plantdoc_eval.json").write_text(json.dumps(report, indent=2))
print("DONE. files:", [p.name for p in OUT.iterdir()], flush=True)
