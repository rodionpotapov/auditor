# tests/test_crud.py

import sys, pathlib
# Корень проекта = папка выше tests/
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
_TESTS_DIR    = str(pathlib.Path(__file__).parent)
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _TESTS_DIR    not in sys.path: sys.path.insert(0, _TESTS_DIR)
_SRC_DIR = str(pathlib.Path(__file__).parent.parent / 'src')
if _SRC_DIR not in sys.path: sys.path.insert(0, _SRC_DIR)

import pytest
import db_mock

from sqlalchemy.orm import sessionmaker
from src import config as _cfg
from src import crud

_engine = db_mock._engine
_models = db_mock._mmod




@pytest.fixture
def db():
    Session = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()


# ── Companies ──

class TestCompanies:

    def test_create_company(self, db):
        c = crud.create_company(db, "ООО Тест")
        assert c.id is not None
        assert c.name == "ООО Тест"

    def test_create_creates_boosters(self, db):
        c = crud.create_company(db, "ООО Тест")
        b = crud.get_boosters(db, c.id)
        assert b is not None
        assert b.boost_manual == _cfg.BOOST_MANUAL

    def test_create_creates_whitelist(self, db):
        c     = crud.create_company(db, "ООО Тест")
        rules = crud.get_whitelist(db, c.id)
        assert len(rules) == len(_cfg.WHITELIST_DOC_TYPES) + len(_cfg.WHITELIST_PAIRS)

    def test_create_creates_api_key(self, db):
        c    = crud.create_company(db, "ООО Тест")
        keys = crud.get_api_keys(db, c.id)
        assert len(keys) == 1

    def test_get_company(self, db):
        c = crud.create_company(db, "ООО Найти")
        assert crud.get_company(db, c.id).name == "ООО Найти"

    def test_get_company_not_found(self, db):
        assert crud.get_company(db, 99999) is None

    def test_get_by_name(self, db):
        crud.create_company(db, "ООО Ромашка")
        assert crud.get_company_by_name(db, "ООО Ромашка") is not None

    def test_get_by_name_not_found(self, db):
        assert crud.get_company_by_name(db, "Несуществующая") is None

    def test_delete_company(self, db):
        c = crud.create_company(db, "ООО Удалить")
        assert crud.delete_company(db, c.id) is True
        assert crud.get_company(db, c.id) is None

    def test_delete_cascades_whitelist(self, db):
        c = crud.create_company(db, "ООО Каскад")
        crud.delete_company(db, c.id)
        assert crud.get_whitelist(db, c.id) == []

    def test_delete_cascades_boosters(self, db):
        c = crud.create_company(db, "ООО Каскад2")
        crud.delete_company(db, c.id)
        assert crud.get_boosters(db, c.id) is None

    def test_delete_nonexistent(self, db):
        assert crud.delete_company(db, 99999) is False

    def test_get_all_companies(self, db):
        crud.create_company(db, "Альфа")
        crud.create_company(db, "Бета")
        assert len(crud.get_companies(db)) == 2


# ── API Keys ──

class TestApiKeys:

    def test_create_key(self, db):
        c   = crud.create_company(db, "ООО Ключ")
        key = crud.create_api_key(db, c.id)
        assert len(key.key) == 64

    def test_get_keys(self, db):
        c = crud.create_company(db, "ООО Ключ2")
        crud.create_api_key(db, c.id)
        assert len(crud.get_api_keys(db, c.id)) == 2  # 1 при создании + 1 явно

    def test_delete_key(self, db):
        c   = crud.create_company(db, "ООО Дел")
        key = crud.create_api_key(db, c.id)
        assert crud.delete_api_key(db, key.id) is True

    def test_delete_nonexistent(self, db):
        assert crud.delete_api_key(db, 99999) is False

    def test_find_company_by_key(self, db):
        c    = crud.create_company(db, "ООО Поиск")
        keys = crud.get_api_keys(db, c.id)
        assert crud.get_company_by_api_key(db, keys[0].key).id == c.id

    def test_invalid_key_returns_none(self, db):
        assert crud.get_company_by_api_key(db, "bad_key") is None

    def test_keys_are_unique(self, db):
        c  = crud.create_company(db, "ООО Уник")
        k1 = crud.create_api_key(db, c.id)
        k2 = crud.create_api_key(db, c.id)
        assert k1.key != k2.key


# ── Whitelist ──

class TestWhitelist:

    def test_add_doc_type(self, db):
        c      = crud.create_company(db, "ООО WL")
        before = len(crud.get_whitelist(db, c.id))
        crud.add_whitelist_rule(db, c.id, "doc_type", doc_type="Ручная операция")
        assert len(crud.get_whitelist(db, c.id)) == before + 1

    def test_add_pair(self, db):
        c      = crud.create_company(db, "ООО WL2")
        before = len(crud.get_whitelist(db, c.id))
        crud.add_whitelist_rule(db, c.id, "pair", account_pair="71.01_50.02")
        assert len(crud.get_whitelist(db, c.id)) == before + 1

    def test_no_duplicates(self, db):
        c = crud.create_company(db, "ООО Дубль")
        crud.add_whitelist_rule(db, c.id, "doc_type", doc_type="УникальныйТип")
        crud.add_whitelist_rule(db, c.id, "doc_type", doc_type="УникальныйТип")
        rules = [r for r in crud.get_whitelist(db, c.id) if r.doc_type == "УникальныйТип"]
        assert len(rules) == 1

    def test_delete_rule(self, db):
        c    = crud.create_company(db, "ООО Дел")
        rule = crud.add_whitelist_rule(db, c.id, "doc_type", doc_type="Удалить")
        assert crud.delete_whitelist_rule(db, rule.id) is True
        assert not any(r.doc_type == "Удалить" for r in crud.get_whitelist(db, c.id))

    def test_delete_nonexistent(self, db):
        assert crud.delete_whitelist_rule(db, 99999) is False

    def test_isolated_per_company(self, db):
        c1 = crud.create_company(db, "А")
        c2 = crud.create_company(db, "Б")
        crud.add_whitelist_rule(db, c1.id, "doc_type", doc_type="ТолькоАльфа")
        assert not any(r.doc_type == "ТолькоАльфа" for r in crud.get_whitelist(db, c2.id))


# ── Boosters ──

class TestBoosters:

    def test_defaults_from_config(self, db):
        c = crud.create_company(db, "ООО Буст")
        b = crud.get_boosters(db, c.id)
        assert b.boost_manual         == _cfg.BOOST_MANUAL
        assert b.boost_amount_outlier == _cfg.BOOST_AMOUNT_OUTLIER
        assert b.boost_night          == _cfg.BOOST_NIGHT

    def test_update(self, db):
        c = crud.create_company(db, "ООО БустUpd")
        crud.update_boosters(db, c.id, boost_manual=1.7, boost_night=1.4)
        b = crud.get_boosters(db, c.id)
        assert b.boost_manual == 1.7
        assert b.boost_night  == 1.4

    def test_partial_update(self, db):
        c = crud.create_company(db, "ООО Частичный")
        crud.update_boosters(db, c.id, boost_manual=1.7)
        b = crud.get_boosters(db, c.id)
        assert b.boost_amount_outlier == _cfg.BOOST_AMOUNT_OUTLIER

    def test_isolated_per_company(self, db):
        c1 = crud.create_company(db, "БустА")
        c2 = crud.create_company(db, "БустБ")
        crud.update_boosters(db, c1.id, boost_manual=1.7)
        assert crud.get_boosters(db, c2.id).boost_manual == _cfg.BOOST_MANUAL

    def test_lof_n_neighbors_default(self, db):
        c = crud.create_company(db, "ООО LOF")
        b = crud.get_boosters(db, c.id)
        assert b.lof_n_neighbors == 50

    def test_lof_n_neighbors_update(self, db):
        c = crud.create_company(db, "ООО LOF2")
        crud.update_boosters(db, c.id, lof_n_neighbors=20)
        b = crud.get_boosters(db, c.id)
        assert b.lof_n_neighbors == 20


# ── History ──

class TestHistory:

    def test_add(self, db):
        c = crud.create_company(db, "ООО Хист")
        r = crud.add_history(db, c.id, "File.csv", 1000, 35, 5)
        assert r.id is not None
        assert r.filename == "File.csv"

    def test_ordered_desc(self, db):
        c = crud.create_company(db, "ООО Порядок")
        for i in range(3):
            crud.add_history(db, c.id, f"f{i}.csv", 100, i * 10, i)
        records    = crud.get_history(db, c.id)
        timestamps = [r.timestamp for r in records]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_delete(self, db):
        c = crud.create_company(db, "ООО ДелХист")
        r = crud.add_history(db, c.id, "del.csv", 100, 5, 1)
        assert crud.delete_history_record(db, r.id) is True
        assert crud.get_history(db, c.id) == []

    def test_isolated_per_company(self, db):
        c1 = crud.create_company(db, "Хист А")
        c2 = crud.create_company(db, "Хист Б")
        crud.add_history(db, c1.id, "f.csv", 100, 5, 1)
        assert crud.get_history(db, c2.id) == []
