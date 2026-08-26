"""Generate the checked-in voice fixture audio in tests/voice/fixtures/.

Run once (or whenever the fixture text changes) with the project venv,
which has the voice-stack dependencies installed:

    .venv/Scripts/python.exe tools/generate_voice_fixtures.py

Produces short, real TTS output (not synthetic silence or noise) for
both v1 languages, via AI4BharatVoiceService.text_to_speech — the same
code path tests/voice/test_ai4bharat_integration.py exercises for ASR.
Kept short deliberately so the checked-in files stay small.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from agro_mirai.voice import AI4BharatVoiceService  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "voice" / "fixtures"

FIXTURES = {
    "en_sample.wav": ("en", "Apply irrigation now."),
    "kn_sample.wav": ("kn", "ಈಗ ನೀರಾವರಿ ಮಾಡಿ."),  # "Apply irrigation now."
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    svc = AI4BharatVoiceService(model_dir=REPO_ROOT / "models" / "voice")
    for filename, (lang, text) in FIXTURES.items():
        audio = svc.text_to_speech(text, lang)
        out_path = FIXTURES_DIR / filename
        out_path.write_bytes(audio)
        print(f"wrote {out_path} ({len(audio)} bytes) — lang={lang!r} text={text!r}")


if __name__ == "__main__":
    main()
