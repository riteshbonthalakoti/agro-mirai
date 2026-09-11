"""Route-level tests for the voice inference service, using a stub
VoiceService — no torch/AI4Bharat weights needed (mirrors
services/cnn-inference/tests's isolation pattern)."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402


class _StubVoice:
    def translate(self, text, source_lang, target_lang):
        return f"[{target_lang}] {text}"

    def speech_to_text(self, audio_bytes, expected_lang=None):
        return "recognized text", expected_lang or "en"

    def text_to_speech(self, text, lang):
        # A real, valid (tiny, silent) WAV — Module 23's /text-to-speech
        # route genuinely transcodes this through ffmpeg to OGG, so the
        # stub has to hand it real WAV bytes, not a fake RIFF-prefixed
        # string ffmpeg would reject.
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 100)
        return buf.getvalue()


def _client(service_factory):
    app = create_app(service_factory=service_factory)
    app.config["TESTING"] = True
    return app.test_client()


def test_health_ok():
    client = _client(lambda: _StubVoice())
    resp = client.get("/health")
    assert resp.get_json()["status"] == "ok"


def test_translate_success():
    client = _client(lambda: _StubVoice())
    resp = client.post("/translate", json={"text": "hello", "source_lang": "en", "target_lang": "kn"})
    assert resp.status_code == 200
    assert resp.get_json()["text"] == "[kn] hello"


def test_translate_success_te():
    # Module 25: this route is language-agnostic — it hands whatever
    # target_lang it's given straight to the VoiceService, which is where
    # real V1_LANGUAGES gating lives (tests/voice/test_interface_conformance.py).
    # Confirms te/hi aren't rejected at the HTTP layer for some unrelated
    # reason (stale allowlist, etc).
    client = _client(lambda: _StubVoice())
    resp = client.post("/translate", json={"text": "hello", "source_lang": "en", "target_lang": "te"})
    assert resp.status_code == 200
    assert resp.get_json()["text"] == "[te] hello"


def test_translate_success_hi():
    client = _client(lambda: _StubVoice())
    resp = client.post("/translate", json={"text": "hello", "source_lang": "en", "target_lang": "hi"})
    assert resp.status_code == 200
    assert resp.get_json()["text"] == "[hi] hello"


def test_translate_missing_field_400():
    client = _client(lambda: _StubVoice())
    resp = client.post("/translate", json={"text": "hello"})
    assert resp.status_code == 400


def test_speech_to_text_success():
    client = _client(lambda: _StubVoice())
    data = {"audio": (io.BytesIO(b"fake"), "clip.wav"), "expected_lang": "en"}
    resp = client.post("/speech-to-text", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text"] == "recognized text"
    assert body["detected_lang"] == "en"


def test_speech_to_text_success_te_expected_lang():
    client = _client(lambda: _StubVoice())
    data = {"audio": (io.BytesIO(b"fake"), "clip.wav"), "expected_lang": "te"}
    resp = client.post("/speech-to-text", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["detected_lang"] == "te"


def test_speech_to_text_success_hi_expected_lang():
    client = _client(lambda: _StubVoice())
    data = {"audio": (io.BytesIO(b"fake"), "clip.wav"), "expected_lang": "hi"}
    resp = client.post("/speech-to-text", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.get_json()["detected_lang"] == "hi"


def test_speech_to_text_missing_audio_400():
    client = _client(lambda: _StubVoice())
    resp = client.post("/speech-to-text", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_text_to_speech_success(monkeypatch):
    # Mock the transcode so this test verifies route wiring (stub TTS →
    # transcode → audio/ogg response), not whether ffmpeg is installed on
    # the test machine. The transcode function itself is covered by the
    # ffmpeg-missing test below and by CI's explicit ffmpeg install step.
    import app as app_module

    monkeypatch.setattr(app_module, "_transcode_wav_to_ogg", lambda wav: b"OggS\x00fake")
    client = _client(lambda: _StubVoice())
    resp = client.post("/text-to-speech", json={"text": "hello", "lang": "en"})
    assert resp.status_code == 200
    assert resp.content_type == "audio/ogg"
    assert resp.data.startswith(b"OggS")


def test_text_to_speech_success_hi(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "_transcode_wav_to_ogg", lambda wav: b"OggS\x00fake")
    client = _client(lambda: _StubVoice())
    resp = client.post("/text-to-speech", json={"text": "hello", "lang": "hi"})
    assert resp.status_code == 200
    assert resp.content_type == "audio/ogg"


def test_text_to_speech_ffmpeg_missing_returns_422_not_500(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module.shutil, "which", lambda name: None)
    client = _client(lambda: _StubVoice())
    resp = client.post("/text-to-speech", json={"text": "hello", "lang": "en"})
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "VOICE_ERROR"


def test_model_unavailable_returns_503_not_500():
    def _boom():
        raise FileNotFoundError("weights missing")

    client = _client(_boom)
    data = {"audio": (io.BytesIO(b"fake"), "clip.wav")}
    resp = client.post("/speech-to-text", data=data, content_type="multipart/form-data")
    assert resp.status_code == 503
