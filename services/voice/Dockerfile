# Voice inference service — AI4Bharat stack, own container, deployed on
# the Oracle VM alongside services/cnn-inference (see
# decisions/0019-deployment-architecture.md and
# docs/deploy/oracle-vm-setup.md). Same ARM64/aarch64 wheel-availability
# caveat as services/cnn-inference/Dockerfile applies to torch here too
# — NOT verified on real arm64 hardware in this session, documented as a
# risk, not asserted as working. AI4Bharat's own model weights (~6.8GB,
# per Module 12's docs/TOOLING.md) are downloaded on first run from
# Hugging Face, not baked into the image — this container needs outbound
# internet on first boot and a persistent volume for the HF cache so
# that download doesn't repeat on every restart.

FROM python:3.12-slim

# ffmpeg — Module 23: transcodes Piper's native WAV output to OGG/Vorbis
# before /text-to-speech responds, so the main API's TTS endpoint never
# has to ship raw WAV to a mobile client.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/voice/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/agro_mirai /app/agro_mirai_pkg/agro_mirai
ENV PYTHONPATH=/app/agro_mirai_pkg

COPY services/voice/app.py ./app.py

# Hugging Face model cache — mount a named volume here so the ~6.8GB
# download only happens once, not on every container restart.
ENV HF_HOME=/hf-cache
VOLUME ["/hf-cache"]

EXPOSE 8002

# --timeout 300: first request after a cold start triggers model
# download + load, which took ~2 minutes even on the dev machine in
# Module 12 (docs/architecture.md) — a modest Ampere A1 core could be
# slower still.
CMD ["gunicorn", "-w", "1", "--timeout", "300", "-b", "0.0.0.0:8002", "app:app"]
