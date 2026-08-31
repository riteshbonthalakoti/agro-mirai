# CNN inference service — standalone container, deployed independently
# of the main Render-hosted API (see decisions/0019-deployment-architecture.md).
#
# ARM64/aarch64 note (Oracle Ampere A1 free-tier shape target): PyTorch
# publishes official linux/aarch64 CPU wheels on download.pytorch.org for
# recent 2.x releases, and manylinux aarch64 wheels are also on PyPI for
# torch/torchvision as of the versions pinned in requirements.txt — but
# this was NOT verified by actually building this image on arm64 hardware
# in this session (no Oracle VM exists yet). Treat this as a real risk,
# not a guarantee: build and smoke-test this image ON the Oracle VM
# itself before relying on it, and if the aarch64 wheel resolution fails,
# fall back to `--platform linux/amd64` emulation (slower, but a known
# escape hatch) or building torch from source (last resort, very slow).

FROM python:3.12-slim

# Minimal system deps for Pillow (libjpeg/zlib) — the slim base doesn't
# ship these by default.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/cnn-inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The main agro_mirai package is needed for
# agro_mirai.models.image_disease_risk_model / disease_cnn_labels /
# disease_risk_scoring / persistence.models — copy just the src tree,
# not the whole repo (tests, docs, etc. aren't needed in the image).
COPY src/agro_mirai /app/agro_mirai_pkg/agro_mirai
ENV PYTHONPATH=/app/agro_mirai_pkg

COPY services/cnn-inference/app.py ./app.py

# Trained artifacts are gitignored and NOT baked into this image — see
# README.md "Getting the trained artifact onto the VM". Mounted as a
# volume at container run time, expected at /models by default.
ENV CNN_WEIGHTS_PATH=/models/disease_cnn_mobilenetv2.pt
ENV CNN_CLASS_NAMES_PATH=/models/disease_cnn_class_names.json

EXPOSE 8001

# --timeout 120: a cold CPU MobileNetV2 forward pass plus model load on
# first request can take longer than gunicorn's 30s default worker
# timeout on a modest Ampere A1 core count.
CMD ["gunicorn", "-w", "1", "--timeout", "120", "-b", "0.0.0.0:8001", "app:app"]
