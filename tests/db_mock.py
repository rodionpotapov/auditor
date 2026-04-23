# tests/db_mock.py
"""
Подменяет src.database на SQLite in-memory для тестов.
Импортировать ПЕРВЫМ до любых модулей проекта.
"""

import sys, pathlib
# Корень проекта = папка выше tests/
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
_TESTS_DIR    = str(pathlib.Path(__file__).parent)
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _TESTS_DIR    not in sys.path: sys.path.insert(0, _TESTS_DIR)
# Добавляем src/ чтобы работал как 'import config' так и 'from src.config import ...'
_SRC_DIR = str(pathlib.Path(__file__).parent.parent / 'src')
if _SRC_DIR not in sys.path: sys.path.insert(0, _SRC_DIR)
import types


# Регистрируем пустой пакет src
if 'src' not in sys.modules:
    sys.modules['src'] = types.ModuleType('src')

# ── Патчим src.config ──
import config as _cfg
sys.modules['src.config'] = _cfg

# ── Создаём фейковый src.database с SQLite ──
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

class Base(DeclarativeBase):
    pass

_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

def get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Создаём модуль-заглушку
_db_mod = types.ModuleType('src.database')
_db_mod.engine       = _engine
_db_mod.SessionLocal = _SessionLocal
_db_mod.Base         = Base
_db_mod.get_db       = get_db
sys.modules['src.database'] = _db_mod
sys.modules['database']     = _db_mod  # для прямого импорта

# ── Теперь импортируем models (зависит от src.database.Base) ──
# Патчим models.py чтобы использовал нашу Base
import importlib.util, pathlib

spec = importlib.util.spec_from_file_location("models_real", pathlib.Path(__file__).parent.parent / "src" / "models.py")
_mmod  = importlib.util.module_from_spec(spec)

# Подменяем Base до выполнения models.py
_mmod.__dict__['Base'] = Base

# Нужно чтобы from src.database import Base вернул нашу Base
spec.loader.exec_module(_mmod)

sys.modules['src.models'] = _mmod
sys.modules['models']     = _mmod

# ── Создаём таблицы ──
Base.metadata.create_all(bind=_engine)

# ── Импортируем crud ──
import crud as _crud_real          # прямой импорт, т.к. _SRC_DIR уже в sys.path
sys.modules['src.crud'] = _crud_real
sys.modules['crud']     = _crud_real

# ── Заглушки недостающих модулей src.* ──

import pandas as pd
import numpy as np

# src.data_processing
_dp = types.ModuleType('src.data_processing')
def _load_data(file):
    return pd.DataFrame([{
        "Период": "2023-06-15 10:00:00", "СчетДт": "51", "СчетКт": "62.01",
        "ВалютнаяСуммаДт": "15 000,00", "ТипДокумента": "Поступление на расчетный счет",
        "Контрагент": "ООО Тест", "Содержание": "Оплата", "ВидДвижения": "Дебет",
        "Организация": "ООО Тест",
    }])
def _clean_data(df): return df
_dp.load_data  = _load_data
_dp.clean_data = _clean_data
sys.modules['src.data_processing'] = _dp

# src.build_features
_bf = types.ModuleType('src.build_features')
def _build_features(df):
    df = df.copy()
    for col in ["hour","day_of_week","month","is_weekend","is_night","is_mounth_end",
                "is_quarter_end","log_amount","is_negative_amount","amount_zscore",
                "is_amount_outlier","log_pair_frequency","is_rare_pair","account_dt_freq",
                "account_kt_freq","account_pair_freq","log_contractor_frequency",
                "is_first_operation","is_first_contractor_pair","large_and_rare",
                "late_and_large","new_cont_and_large","manual_and_large","daily_volume",
                "hourly_volume","time_since_last_contractor","time_since_last_pair",
                "ТипДокумента_freq","is_manual"]:
        df[col] = 0
    df["abs_amount"]    = 15000.0
    df["account_pair"]  = "51_62.01"
    df["account_dt"]    = "51"
    df["account_kt"]    = "62.01"
    df["pair_mean"]     = 15000.0
    df["ensemble_score"] = 0.1
    df["СчетДт"]        = df.get("СчетДт", "51")
    df["СчетКт"]        = df.get("СчетКт", "62.01")
    X = df[["is_manual"]].values
    return df, X
_bf.build_features = _build_features
sys.modules['src.build_features'] = _bf

# src.model
_ml = types.ModuleType('src.model')
def _train_and_score(df, X, lof_n_neighbors=50):
    df = df.copy()
    df["ensemble_score"] = np.random.uniform(0, 0.3, len(df))
    return df
_ml.train_and_score = _train_and_score
sys.modules['src.model'] = _ml

# src.report_generator
_rg = types.ModuleType('src.report_generator')
def _generate_report(df, top_n=2000):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Тест"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
_rg.generate_report = _generate_report
sys.modules['src.report_generator'] = _rg

# src.scoring
import scoring as _sc_real
sys.modules['src.scoring'] = _sc_real
