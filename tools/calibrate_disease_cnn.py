"""Temperature-scale the fine-tuned disease CNN and pick the 'not sure' threshold.

Run in the SAME Colab kernel right after train_disease_cnn_plantdoc.py (it reuses
its variables: model, pd_val_dl, pd_test_dl, pv_hold_dl, metrics, dev).

Fits one temperature T on the PlantDoc VALIDATION slice (never the test split)
so that softmax(logits / T) confidences match how often the model is right,
then reports the PlantDoc test split before/after and an accuracy-vs-coverage
table for candidate 'not sure' thresholds.
"""
import json

import numpy as np
import torch
import torch.nn.functional as F

model.to(dev).eval()  # noqa: F821


@torch.no_grad()
def logits_of(dl):
    ls, ys = [], []
    for x, y in dl:
        ls.append(model(x.to(dev)).cpu())  # noqa: F821
        ys.append(y)
    return torch.cat(ls), torch.cat(ys)


val_l, val_y = logits_of(pd_val_dl)  # noqa: F821
test_l, test_y = logits_of(pd_test_dl)  # noqa: F821
pv_l, pv_y = logits_of(pv_hold_dl)  # noqa: F821

best_t, best_nll = 1.0, 1e9
for t in np.arange(0.5, 4.01, 0.05):
    nll = F.cross_entropy(val_l / float(t), val_y).item()
    if nll < best_nll:
        best_t, best_nll = float(t), nll
best_t = round(best_t, 2)
print("fitted temperature (PlantDoc val):", best_t, flush=True)


def report(l, y, t):
    probs = F.softmax(l / t, 1).numpy()
    return metrics(probs, y.numpy())  # noqa: F821


out = {
    "temperature": best_t,
    "plantdoc_test_T1": report(test_l, test_y, 1.0),
    "plantdoc_test_fitted": report(test_l, test_y, best_t),
    "plantvillage_T1": report(pv_l, pv_y, 1.0),
    "plantvillage_fitted": report(pv_l, pv_y, best_t),
}
probs = F.softmax(test_l / best_t, 1).numpy()
pred, conf, y = probs.argmax(1), probs.max(1), test_y.numpy()
table = []
for thr in (0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8):
    m = conf >= thr
    table.append({
        "threshold": thr, "share_answered": float(m.mean()),
        "accuracy_when_answered": float((pred[m] == y[m]).mean()) if m.any() else None,
    })
out["plantdoc_test_threshold_table_fitted"] = table
print(json.dumps(out, indent=1), flush=True)
open("/content/out/calibration.json", "w").write(json.dumps(out, indent=2))
