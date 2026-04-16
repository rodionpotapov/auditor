# tests/test_api.py

import sys, pathlib
# Корень проекта = папка выше tests/
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
_TESTS_DIR    = str(pathlib.Path(__file__).parent)
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _TESTS_DIR    not in sys.path: sys.path.insert(0, _TESTS_DIR)
_SRC_DIR = str(pathlib.Path(__file__).parent.parent / 'src')
if _SRC_DIR not in sys.path: sys.path.insert(0, _SRC_DIR)
import sys, json, io

import pytest
import db_mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src import config as _cfg
from src import crud as _crud

_engine = db_mock._engine
_models = db_mock._mmod
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

# Патчим get_db в api.py на тестовую сессию
def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

import api as _api
from database import get_db
_api.app.dependency_overrides[get_db] = _override_get_db

client = TestClient(_api.app)




def _company(name="ООО Тест"):
    r = client.post("/companies/", json={"name": name})
    assert r.status_code == 200
    return r.json()


# ── Companies ──

class TestCompaniesEndpoints:

    def test_create(self):
        r = client.post("/companies/", json={"name": "ООО Альфа"})
        assert r.status_code == 200
        assert r.json()["name"] == "ООО Альфа"

    def test_create_idempotent(self):
        r1 = client.post("/companies/", json={"name": "Дубль"}).json()
        r2 = client.post("/companies/", json={"name": "Дубль"}).json()
        assert r1["id"] == r2["id"]

    def test_list(self):
        client.post("/companies/", json={"name": "А"})
        client.post("/companies/", json={"name": "Б"})
        assert len(client.get("/companies/").json()) == 2

    def test_delete(self):
        c = _company("ООО Дел")
        r = client.delete(f"/companies/{c['id']}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_delete_404(self):
        assert client.delete("/companies/99999").status_code == 404


# ── API Keys ──

class TestApiKeysEndpoints:

    def test_get_keys(self):
        c = _company()
        r = client.get(f"/companies/{c['id']}/api-keys/")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_create_key(self):
        c      = _company()
        before = len(client.get(f"/companies/{c['id']}/api-keys/").json())
        client.post(f"/companies/{c['id']}/api-keys/")
        after  = len(client.get(f"/companies/{c['id']}/api-keys/").json())
        assert after == before + 1

    def test_delete_key(self):
        c    = _company()
        keys = client.get(f"/companies/{c['id']}/api-keys/").json()
        r    = client.delete(f"/api-keys/{keys[0]['id']}")
        assert r.status_code == 200

    def test_delete_key_404(self):
        assert client.delete("/api-keys/99999").status_code == 404


# ── Whitelist ──

class TestWhitelistEndpoints:

    def test_get(self):
        c = _company()
        r = client.get(f"/companies/{c['id']}/whitelist/")
        assert r.status_code == 200
        assert len(r.json()["rules"]) > 0  # дефолтные правила

    def test_add_doc_type(self):
        c      = _company()
        before = len(client.get(f"/companies/{c['id']}/whitelist/").json()["rules"])
        r      = client.post(f"/companies/{c['id']}/whitelist/",
                             json={"type": "doc_type", "doc_type": "Ручная операция"})
        assert r.status_code == 200
        after  = len(client.get(f"/companies/{c['id']}/whitelist/").json()["rules"])
        assert after == before + 1

    def test_add_pair(self):
        c = _company()
        r = client.post(f"/companies/{c['id']}/whitelist/",
                        json={"type": "pair", "account_pair": "71.01_50.02", "doc_type": ""})
        assert r.status_code == 200
        assert r.json()["account_pair"] == "71.01_50.02"

    def test_delete_rule(self):
        c    = _company()
        rule = client.post(f"/companies/{c['id']}/whitelist/",
                           json={"type": "doc_type", "doc_type": "УдалитьМеня"}).json()
        r    = client.delete(f"/whitelist/{rule['id']}")
        assert r.status_code == 200

    def test_delete_rule_404(self):
        assert client.delete("/whitelist/99999").status_code == 404

    def test_export(self):
        c    = _company()
        r    = client.get(f"/companies/{c['id']}/whitelist/export/")
        assert r.status_code == 200
        data = r.json()
        assert "rules" in data
        assert len(data["rules"]) > 0

    def test_import(self):
        c       = _company()
        payload = json.dumps({"rules": [
            {"type": "doc_type", "doc_type": "ИмпортТип", "account_pair": ""}
        ]})
        r = client.post(
            f"/companies/{c['id']}/whitelist/import/",
            files={"file": ("wl.json", payload.encode(), "application/json")},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_import_invalid_json(self):
        c = _company()
        r = client.post(
            f"/companies/{c['id']}/whitelist/import/",
            files={"file": ("wl.json", b"not json", "application/json")},
        )
        assert r.status_code == 400


# ── Boosters ──

class TestBoostersEndpoints:

    def test_get(self):
        c = _company()
        r = client.get(f"/companies/{c['id']}/boosters/")
        assert r.status_code == 200
        assert r.json()["boost_manual"] == _cfg.BOOST_MANUAL

    def test_update(self):
        c = _company()
        client.put(f"/companies/{c['id']}/boosters/", json={
            "boost_manual": 1.7, "boost_amount_outlier": 1.4,
            "boost_night": 1.4, "boost_first_operation": 1.3,
            "boost_suspicious_pair": 1.7,
        })
        assert client.get(f"/companies/{c['id']}/boosters/").json()["boost_manual"] == 1.7

    def test_get_404(self):
        assert client.get("/companies/99999/boosters/").status_code == 404


# ── История ──

class TestHistoryEndpoints:

    def test_empty(self):
        c = _company()
        r = client.get(f"/companies/{c['id']}/history/")
        assert r.status_code == 200
        assert r.json()["runs"] == []

    def test_delete(self):
        c  = _company()
        db = _SessionLocal()
        rec = _crud.add_history(db, c["id"], "f.csv", 100, 5, 1)
        db.close()
        assert client.delete(f"/history/{rec.id}").status_code == 200

    def test_delete_404(self):
        assert client.delete("/history/99999").status_code == 404


# ── Autocomplete ──

class TestAutocomplete:

    def test_returns_data(self):
        r = client.get("/autocomplete/")
        assert r.status_code == 200
        d = r.json()
        assert len(d["doc_types"]) > 0
        assert len(d["accounts"]) > 0


# ── Анализ (UI) ──

# db_mock полностью перехватывает load_data, поэтому реальный CSV не нужен
_CSV_STUB = b"stub csv content"


class TestAnalyzeEndpoints:

    def test_analyze_company_not_found(self):
        r = client.post(
            "/analyze/99999/",
            files={"file": ("test.csv", _CSV_STUB, "text/csv")},
        )
        assert r.status_code == 404

    def test_analyze_returns_xlsx(self):
        c = _company()
        r = client.post(
            f"/analyze/{c['id']}/",
            files={"file": ("test.csv", _CSV_STUB, "text/csv")},
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "anomalies.xlsx" in r.headers.get("content-disposition", "")

    def test_analyze_adds_history(self):
        c = _company()
        client.post(
            f"/analyze/{c['id']}/",
            files={"file": ("data.csv", _CSV_STUB, "text/csv")},
        )
        runs = client.get(f"/companies/{c['id']}/history/").json()["runs"]
        assert len(runs) == 1
        assert runs[0]["filename"] == "data.csv"

    def test_analyze_history_has_numeric_fields(self):
        c = _company()
        client.post(
            f"/analyze/{c['id']}/",
            files={"file": ("data.csv", _CSV_STUB, "text/csv")},
        )
        run = client.get(f"/companies/{c['id']}/history/").json()["runs"][0]
        assert isinstance(run["dataset_rows"], int)
        assert isinstance(run["total"], int)
        assert isinstance(run["high_risk"], int)


# ── Анализ (внешний API по ключу) ──

class TestExternalAnalyze:

    def test_valid_key_returns_xlsx(self):
        c = _company()
        api_key = client.get(f"/companies/{c['id']}/api-keys/").json()[0]["key"]
        r = client.post(
            "/api/analyze/",
            files={"file": ("test.csv", _CSV_STUB, "text/csv")},
            headers={"x-api-key": api_key},
        )
        assert r.status_code == 200
        assert "xlsx" in r.headers.get("content-disposition", "")

    def test_invalid_key_returns_401(self):
        r = client.post(
            "/api/analyze/",
            files={"file": ("test.csv", _CSV_STUB, "text/csv")},
            headers={"x-api-key": "totally_wrong_key"},
        )
        assert r.status_code == 401

    def test_missing_key_returns_422(self):
        """Заголовок x-api-key обязателен — FastAPI вернёт 422."""
        r = client.post(
            "/api/analyze/",
            files={"file": ("test.csv", _CSV_STUB, "text/csv")},
        )
        assert r.status_code == 422
