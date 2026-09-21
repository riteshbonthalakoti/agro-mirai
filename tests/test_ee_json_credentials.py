"""Module 40: on Render there is no key file, so the Earth Engine service
account can be supplied as JSON text in EE_SERVICE_ACCOUNT_JSON. ``ee`` and
Google's loader are stubbed: no network, no earthengine-api install needed."""
import json
import sys
import types

from agro_mirai.acquisition.earth_engine import NDVIAdapter


def _stub_modules(monkeypatch):
    seen = {}
    ee = types.ModuleType("ee")
    ee.oauth = types.SimpleNamespace(SCOPES=["scope-a"])
    ee.Initialize = lambda creds, project=None: seen.update(creds=creds, project=project)
    ee.ServiceAccountCredentials = lambda *a, **k: seen.update(file_path_used=True)
    google = types.ModuleType("google")
    oauth2 = types.ModuleType("google.oauth2")
    sa_mod = types.ModuleType("google.oauth2.service_account")
    sa_mod.Credentials = types.SimpleNamespace(
        from_service_account_info=lambda info, scopes: ("creds", info["client_email"], tuple(scopes))
    )
    oauth2.service_account = sa_mod
    google.oauth2 = oauth2
    for name, mod in (("ee", ee), ("google", google), ("google.oauth2", oauth2), ("google.oauth2.service_account", sa_mod)):
        monkeypatch.setitem(sys.modules, name, mod)
    return seen


def test_json_text_is_used_without_any_key_file(monkeypatch, tmp_path):
    seen = _stub_modules(monkeypatch)
    monkeypatch.delenv("EE_SERVICE_ACCOUNT_KEY", raising=False)
    monkeypatch.setenv(
        "EE_SERVICE_ACCOUNT_JSON", json.dumps({"client_email": "svc@x.iam", "project_id": "proj"})
    )
    NDVIAdapter(cache_path=tmp_path / "c.json")._ensure_initialized()
    assert seen["creds"] == ("creds", "svc@x.iam", ("scope-a",))
    assert seen["project"] == "proj"
    assert "file_path_used" not in seen


def test_key_file_path_still_works_when_no_json(monkeypatch, tmp_path):
    seen = _stub_modules(monkeypatch)
    monkeypatch.delenv("EE_SERVICE_ACCOUNT_JSON", raising=False)
    key = tmp_path / "k.json"
    key.write_text(json.dumps({"client_email": "svc@x.iam", "project_id": "proj"}))
    monkeypatch.setenv("EE_SERVICE_ACCOUNT_KEY", str(key))
    NDVIAdapter(cache_path=tmp_path / "c.json")._ensure_initialized()
    assert seen.get("file_path_used") is True
