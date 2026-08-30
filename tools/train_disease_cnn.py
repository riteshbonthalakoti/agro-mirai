"""Trains the Module 20 disease-classification CNN. Run this on a Colab
GPU runtime (paths are Colab's `/content/...`, not local) — see
`decisions/0018-disease-cnn.md` for the exact reproduction steps
(dataset: Kaggle `abdallahalidev/plantvillage-dataset`, `color/` split
only, MobileNetV2 transfer learning). Not runnable locally as-is: this
repo's main venv deliberately excludes torch/torchvision (same policy as
the Module 12 voice stack — decisions/0014), and CPU training on this
dataset size would be impractically slow anyway.

After training, copy the two output files into `models/`:
  disease_cnn_mobilenetv2.pt   (state_dict)
  disease_cnn_class_names.json (class index -> PlantVillage folder name)
"""
import json
import os
import time

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

DATA_DIR = "/content/data2/plantvillage dataset/color"
OUT_DIR = "/content/out"
os.makedirs(OUT_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("device:", device)

IMG_SIZE = 224
train_tf = transforms.Compose([
    transforms.RandomResizedCrop(IMG_SIZE, scale=(0.8, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])
val_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

full_ds = datasets.ImageFolder(DATA_DIR)
class_names = full_ds.classes
num_classes = len(class_names)
print("num_classes:", num_classes)

n_total = len(full_ds)
n_val = int(n_total * 0.15)
n_train = n_total - n_val
gen = torch.Generator().manual_seed(42)
train_subset, val_subset = random_split(full_ds, [n_train, n_val], generator=gen)

# wrap subsets with distinct transforms
class TransformedSubset(torch.utils.data.Dataset):
    def __init__(self, subset, transform):
        self.subset = subset
        self.transform = transform

    def __len__(self):
        return len(self.subset)

    def __getitem__(self, idx):
        img, label = self.subset[idx]
        return self.transform(img), label

train_ds = TransformedSubset(train_subset, train_tf)
val_ds = TransformedSubset(val_subset, val_tf)

BATCH_SIZE = 64
train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=4, pin_memory=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
for param in model.features.parameters():
    param.requires_grad = False
# unfreeze last few feature blocks for fine-tuning
for param in model.features[-3:].parameters():
    param.requires_grad = True

model.classifier[1] = nn.Linear(model.last_channel, num_classes)
model = model.to(device)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(
    [p for p in model.parameters() if p.requires_grad], lr=1e-3
)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=4, gamma=0.3)

EPOCHS = 8
best_val_acc = 0.0
history = []

for epoch in range(EPOCHS):
    t0 = time.time()
    model.train()
    running_loss, running_correct, seen = 0.0, 0, 0
    for imgs, labels in train_loader:
        imgs, labels = imgs.to(device, non_blocking=True), labels.to(device, non_blocking=True)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * imgs.size(0)
        running_correct += (outputs.argmax(1) == labels).sum().item()
        seen += imgs.size(0)
    train_loss = running_loss / seen
    train_acc = running_correct / seen

    model.eval()
    val_correct, val_seen = 0, 0
    with torch.no_grad():
        for imgs, labels in val_loader:
            imgs, labels = imgs.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            outputs = model(imgs)
            val_correct += (outputs.argmax(1) == labels).sum().item()
            val_seen += imgs.size(0)
    val_acc = val_correct / val_seen
    scheduler.step()

    dt = time.time() - t0
    print(f"epoch {epoch+1}/{EPOCHS} train_loss={train_loss:.4f} train_acc={train_acc:.4f} val_acc={val_acc:.4f} ({dt:.1f}s)")
    history.append({"epoch": epoch + 1, "train_loss": train_loss, "train_acc": train_acc, "val_acc": val_acc})

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), os.path.join(OUT_DIR, "disease_cnn_mobilenetv2.pt"))

with open(os.path.join(OUT_DIR, "class_names.json"), "w") as f:
    json.dump(class_names, f, indent=2)

with open(os.path.join(OUT_DIR, "training_history.json"), "w") as f:
    json.dump({"history": history, "best_val_acc": best_val_acc, "num_classes": num_classes, "img_size": IMG_SIZE}, f, indent=2)

print("DONE best_val_acc=", best_val_acc)
