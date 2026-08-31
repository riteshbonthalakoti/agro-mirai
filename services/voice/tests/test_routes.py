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
        return b"RIFF-fake-wav-bytes"


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


def test_speech_to_text_missing_audio_400():
    client = _client(lambda: _StubVoice())
    resp = client.post("/speech-to-text", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_text_to_speech_success():
    client = _client(lambda: _StubVoice())
    resp = client.post("/text-to-speech", json={"text": "hello", "lang": "en"})
    assert resp.status_code == 200
    assert resp.data.startswith(b"RIFF")


def test_model_unavailable_returns_503_not_500():
    def _boom():
        raise FileNotFoundError("weights missing")

    client = _client(_boom)
    data = {"audio": (io.BytesIO(b"fake"), "clip.wav")}
    resp = client.post("/speech-to-text", data=data, content_type="multipart/form-data")
    assert resp.status_code == 503
