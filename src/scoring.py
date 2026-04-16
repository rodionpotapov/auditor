import json
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

from src.config import (
    SUSPICIOUS_PAIRS, WHITELIST_DOC_TYPES, WHITELIST_PAIRS,
    WHITELIST_REQUIRES_NOT_MANUAL, BOOST_MANUAL, BOOST_AMOUNT_OUTLIER,
    BOOST_NIGHT, BOOST_FIRST_OPERATION, BOOST_SUSPICIOUS_PAIR,
)

# Путь к динамическому whitelist (накапливается через UI)
_DYNAMIC_WL_PATH = Path(__file__).parent.parent / "data" / "whitelist_dynamic.json"


def _load_dynamic_whitelist():
    """Читает правила добавленные через UI."""
    if not _DYNAMIC_WL_PATH.exists():
        return {"doc_types": [], "pairs": []}

    raw = json.loads(_DYNAMIC_WL_PATH.read_text(encoding="utf-8"))
    rules = raw.get("rules", [])

    doc_types = [r["doc_type"] for r in rules if r.get("type") == "doc_type" and r.get("doc_type")]
    pairs     = [
        {"account_pair": r["account_pair"], "doc_type": r.get("doc_type", "")}
        for r in rules
        if r.get("type") == "pair" and r.get("account_pair")
    ]
    return {"doc_types": doc_types, "pairs": pairs}


def normalize_scores(data: pd.DataFrame) -> pd.DataFrame:
    """Нормализует ensemble_score → risk_score (0–100)."""
    scaler = MinMaxScaler(feature_range=(0, 100))
    data["risk_score"] = scaler.fit_transform(
        data[["ensemble_score"]]
    ).flatten().round(1)
    return data


def apply_boosts(data: pd.DataFrame) -> pd.DataFrame:
    """Применяет бустеры — берёт максимальный коэффициент."""

    def get_boost(row):
        boosts = []
        if row["is_manual"] == 1:
            boosts.append(BOOST_MANUAL)
        if row["is_amount_outlier"] == 1:
            boosts.append(BOOST_AMOUNT_OUTLIER)
        if row["is_night"] == 1:
            boosts.append(BOOST_NIGHT)
        if row["is_first_operation"] == 1:
            boosts.append(BOOST_FIRST_OPERATION)
        if row["account_pair"] in SUSPICIOUS_PAIRS:
            boosts.append(BOOST_SUSPICIOUS_PAIR)
        return max(boosts) if boosts else 1.0

    data["boosted_score"] = (
        data.apply(get_boost, axis=1) * data["risk_score"]
    ).clip(0, 100).round(1)

    return data


def apply_whitelist(data: pd.DataFrame) -> pd.DataFrame:
    """
    Обнуляет boosted_score для заведомо нормальных операций.
    Объединяет правила из config.py и динамического whitelist_dynamic.json.
    """
    dynamic = _load_dynamic_whitelist()

    # Объединяем типы документов из config и dynamic whitelist
    all_doc_types = list(set(WHITELIST_DOC_TYPES + dynamic["doc_types"]))

    # Whitelist по типу документа (только если is_manual = 0)
    whitelist_mask = (
        data["ТипДокумента"].isin(all_doc_types) &
        (data["is_manual"] == 0 if WHITELIST_REQUIRES_NOT_MANUAL else True)
    )

    # Объединяем пары из config и dynamic whitelist
    all_pairs = WHITELIST_PAIRS + dynamic["pairs"]

    # Whitelist по паре счетов + тип документа (только если is_manual = 0)
    pairs_mask = pd.Series(False, index=data.index)
    for rule in all_pairs:
        mask = (
            (data["account_pair"] == rule["account_pair"]) &
            (data["is_manual"] == 0)
        )
        # Если тип документа указан — добавляем это условие
        if rule.get("doc_type"):
            mask = mask & (data["ТипДокумента"] == rule["doc_type"])
        pairs_mask = pairs_mask | mask

    data.loc[whitelist_mask | pairs_mask, "boosted_score"] = 0

    n_zeroed = (whitelist_mask | pairs_mask).sum()
    print(f"Обнулено через whitelist: {n_zeroed} строк "
          f"(config: {len(WHITELIST_DOC_TYPES)} типов + {len(WHITELIST_PAIRS)} пар, "
          f"dynamic: {len(dynamic['doc_types'])} типов + {len(dynamic['pairs'])} пар)")

    return data


def explain_anomaly(row) -> str:
    """Генерирует текстовое объяснение аномалии."""
    reasons = []
    if row["is_rare_pair"]:
        reasons.append(f"Редкая пара счетов {row['СчетДт']}→{row['СчетКт']}")
    if row["is_amount_outlier"]:
        reasons.append("Сумма необычно большая для этого типа операции")
    if row["is_night"]:
        reasons.append(f"Операция в нерабочее время ({row['hour']}:00)")
    if row["is_weekend"]:
        reasons.append("Операция в выходной день")
    if row["is_first_operation"]:
        reasons.append("Первая операция с этим контрагентом")
    if row["is_manual"]:
        reasons.append("Ручная проводка")
    if row["is_negative_amount"]:
        reasons.append("Сторно (отрицательная сумма)")
    if row["account_pair"] in SUSPICIOUS_PAIRS:
        reasons.append("Подозрительная пара счетов")
    if not reasons:
        reasons.append("Комбинация факторов")
    return "; ".join(reasons)


def score(data: pd.DataFrame) -> pd.DataFrame:
    """Полный пайплайн скоринга: нормализация → бустеры → whitelist → объяснения."""
    data = normalize_scores(data)
    data = apply_boosts(data)
    data = apply_whitelist(data)
    data["explanation"] = data.apply(explain_anomaly, axis=1)
    return data