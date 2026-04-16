import sys, pathlib

_SRC_DIR = str(pathlib.Path(__file__).parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
# tests/conftest.py

import random
from datetime import datetime, timedelta

import pandas as pd
import pytest


# ─────────────────────────────────────────────
# Генераторы фейковых данных
# ─────────────────────────────────────────────

ACCOUNTS = [
    "50.01",
    "50.02",
    "51",
    "60.01",
    "60.02",
    "62.01",
    "68.90",
    "71.01",
    "76.09",
    "84.01",
    "90.02.1",
    "91.01",
    "91.02",
    "99.01",
]

DOC_TYPES = [
    "Регламентная операция",
    "Отражение зарплаты в бухучете",
    "Закрытие месяца",
    "Списание с расчетного счета",
    "Поступление на расчетный счет",
    "Реализация (акт, накладная, УПД)",
    "Ручная операция",
]

CONTRACTORS = [
    "ООО Ромашка",
    "ИП Иванов",
    "ООО Сервис Плюс",
    "АО Технологии",
    "ООО Логистика",
    "ИП Петров",
]


def make_row(
    *,
    period: str | None = None,
    account_dt: str | None = None,
    account_kt: str | None = None,
    amount: float | None = None,
    doc_type: str | None = None,
    contractor: str | None = None,
    is_manual: int | None = None,
    is_night: int | None = None,
    is_weekend: int | None = None,
    is_amount_outlier: int | None = None,
    is_first_operation: int | None = None,
    is_rare_pair: int | None = None,
    is_negative_amount: int | None = None,
) -> dict:
    """Генерирует одну строку с реалистичными дефолтами."""
    dt = account_dt or random.choice(ACCOUNTS)
    kt = account_kt or random.choice(ACCOUNTS)
    amt = amount if amount is not None else round(random.uniform(1_000, 500_000), 2)

    ts = period or (
        datetime(2023, 1, 1) + timedelta(days=random.randint(0, 364))
    ).strftime("%Y-%m-%d %H:%M:%S")

    hour = int(ts[11:13]) if len(ts) > 10 else random.randint(9, 18)

    return {
        "Период": ts,
        "СчетДт": dt,
        "СчетКт": kt,
        "ВалютнаяСуммаДт": str(amt).replace(".", ","),
        "ТипДокумента": doc_type or random.choice(DOC_TYPES),
        "Контрагент": contractor or random.choice(CONTRACTORS),
        "Содержание": "Тестовая проводка",
        "ВидДвижения": "Дебет",
        "Организация": "ООО Тест",
        # Производные признаки (как после build_features)
        "account_dt": dt,
        "account_kt": kt,
        "account_pair": f"{dt}_{kt}",
        "period": ts,
        "hour": hour,
        "day_of_week": random.randint(0, 6),
        "month": random.randint(1, 12),
        "is_weekend": (
            is_weekend if is_weekend is not None else int(random.random() < 0.2)
        ),
        "is_night": is_night if is_night is not None else int(hour < 8 or hour > 22),
        "is_mounth_end": int(random.random() < 0.1),
        "is_quarter_end": int(random.random() < 0.05),
        "abs_amount": abs(amt),
        "log_amount": round(abs(amt) ** 0.5, 4),
        "is_negative_amount": (
            is_negative_amount if is_negative_amount is not None else int(amt < 0)
        ),
        "amount_zscore": round(random.gauss(0, 1), 3),
        "is_amount_outlier": (
            is_amount_outlier
            if is_amount_outlier is not None
            else int(random.random() < 0.05)
        ),
        "log_pair_frequency": round(random.uniform(0, 5), 3),
        "is_rare_pair": (
            is_rare_pair if is_rare_pair is not None else int(random.random() < 0.1)
        ),
        "account_dt_freq": random.randint(1, 1000),
        "account_kt_freq": random.randint(1, 1000),
        "account_pair_freq": random.randint(1, 500),
        "log_contractor_frequency": round(random.uniform(0, 5), 3),
        "is_first_operation": (
            is_first_operation
            if is_first_operation is not None
            else int(random.random() < 0.05)
        ),
        "is_first_contractor_pair": int(random.random() < 0.05),
        "large_and_rare": int(random.random() < 0.03),
        "late_and_large": int(random.random() < 0.03),
        "new_cont_and_large": int(random.random() < 0.03),
        "manual_and_large": int(random.random() < 0.03),
        "daily_volume": round(random.uniform(0, 1e7), 2),
        "hourly_volume": round(random.uniform(0, 1e6), 2),
        "time_since_last_contractor": round(random.uniform(0, 100), 2),
        "time_since_last_pair": round(random.uniform(0, 100), 2),
        "ТипДокумента_freq": random.randint(1, 5000),
        "is_manual": is_manual if is_manual is not None else int(random.random() < 0.1),
        "pair_mean": round(random.uniform(1_000, 200_000), 2),
        "ensemble_score": round(random.uniform(0, 1), 4),
    }


def make_dataframe(n: int = 100, **kwargs) -> pd.DataFrame:
    """Генерирует датафрейм из n строк."""
    return pd.DataFrame([make_row(**kwargs) for _ in range(n)])


def make_minimal_row() -> dict:
    """Строка только с обязательными колонками CSV (до feature engineering)."""
    return {
        "Период": "2023-06-15 10:00:00",
        "СчетДт": "51",
        "СчетКт": "62.01",
        "ВалютнаяСуммаДт": "15 000,00",
        "ТипДокумента": "Поступление на расчетный счет",
        "Контрагент": "ООО Тест",
        "Содержание": "Оплата по договору",
        "ВидДвижения": "Дебет",
        "Организация": "ООО Тест",
    }


def make_anomalous_row(**kwargs) -> dict:
    """Строка с максимально аномальными признаками."""
    return make_row(
        account_dt="71.01",
        account_kt="50.02",
        amount=9_999_999,
        doc_type="Ручная операция",
        is_manual=1,
        is_night=1,
        is_weekend=1,
        is_amount_outlier=1,
        is_first_operation=1,
        is_rare_pair=1,
        **kwargs,
    )


def make_normal_row(**kwargs) -> dict:
    """Строка заведомо нормальной регламентной операции."""
    return make_row(
        doc_type="Регламентная операция",
        is_manual=0,
        is_night=0,
        is_weekend=0,
        is_amount_outlier=0,
        is_first_operation=0,
        is_rare_pair=0,
        amount=50_000,
        **kwargs,
    )


# ─────────────────────────────────────────────
# Фикстуры pytest
# ─────────────────────────────────────────────


@pytest.fixture
def sample_df():
    """100 смешанных строк."""
    return make_dataframe(100)


@pytest.fixture
def anomalous_df():
    """50 строк — все аномальные."""
    return pd.DataFrame([make_anomalous_row() for _ in range(50)])


@pytest.fixture
def normal_df():
    """50 строк — все нормальные."""
    return pd.DataFrame([make_normal_row() for _ in range(50)])


@pytest.fixture
def mixed_df():
    """Смесь: 80 нормальных + 20 аномальных."""
    rows = [make_normal_row() for _ in range(80)]
    rows += [make_anomalous_row() for _ in range(20)]
    random.shuffle(rows)
    return pd.DataFrame(rows)


@pytest.fixture
def whitelist_doc_type_rule():
    """Мок правила whitelist по типу документа."""

    class R:
        type = "doc_type"
        doc_type = "Регламентная операция"
        account_pair = ""

    return R()


@pytest.fixture
def whitelist_pair_rule():
    """Мок правила whitelist по паре счетов."""

    class R:
        type = "pair"
        doc_type = "Списание с расчетного счета"
        account_pair = "84.01_51"

    return R()


@pytest.fixture
def default_boosters():
    """Мок бустеров с дефолтными значениями."""

    class B:
        boost_manual = 1.5
        boost_amount_outlier = 1.3
        boost_night = 1.3
        boost_first_operation = 1.2
        boost_suspicious_pair = 1.5

    return B()


@pytest.fixture
def max_boosters():
    """Мок бустеров с максимальными значениями."""

    class B:
        boost_manual = 1.7
        boost_amount_outlier = 1.4
        boost_night = 1.4
        boost_first_operation = 1.3
        boost_suspicious_pair = 1.7

    return B()


@pytest.fixture
def min_boosters():
    """Мок бустеров отключённых (1.0 = нет усиления)."""

    class B:
        boost_manual = 1.0
        boost_amount_outlier = 1.0
        boost_night = 1.0
        boost_first_operation = 1.0
        boost_suspicious_pair = 1.0

    return B()


# ── Глобальный сброс БД для тестов api/crud ──


def pytest_configure(config):
    """Добавляем путь к тестам до сбора."""
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parent))


@pytest.fixture(autouse=True)
def reset_test_db():
    """Пересоздаёт таблицы перед каждым тестом."""
    try:
        import db_mock

        db_mock.Base.metadata.drop_all(bind=db_mock._engine)
        db_mock.Base.metadata.create_all(bind=db_mock._engine)
    except ImportError:
        pass  # db_mock не нужен для scoring/fake_data тестов
    yield
