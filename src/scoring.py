# src/scoring.py

import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from src.config import SUSPICIOUS_PAIRS, WHITELIST_REQUIRES_NOT_MANUAL
from src.models import BoosterSettings, WhitelistRule


def normalize_scores(data: pd.DataFrame) -> pd.DataFrame:
    scaler = MinMaxScaler(feature_range=(0, 100))
    data["risk_score"] = scaler.fit_transform(
        data[["ensemble_score"]]
    ).flatten().round(1)
    return data


def apply_boosts(data: pd.DataFrame, boosters: BoosterSettings | None = None) -> pd.DataFrame:
    """Применяет бустеры из БД. Если не переданы — использует дефолты из config."""
    from src.config import (
        BOOST_MANUAL, BOOST_AMOUNT_OUTLIER, BOOST_NIGHT,
        BOOST_FIRST_OPERATION, BOOST_SUSPICIOUS_PAIR,
    )

    bm  = boosters.boost_manual           if boosters else BOOST_MANUAL
    bao = boosters.boost_amount_outlier   if boosters else BOOST_AMOUNT_OUTLIER
    bn  = boosters.boost_night            if boosters else BOOST_NIGHT
    bfo = boosters.boost_first_operation  if boosters else BOOST_FIRST_OPERATION
    bsp = boosters.boost_suspicious_pair  if boosters else BOOST_SUSPICIOUS_PAIR

    def get_boost(row):
        boosts = []
        if row["is_manual"] == 1:           boosts.append(bm)
        if row["is_amount_outlier"] == 1:   boosts.append(bao)
        if row["is_night"] == 1:            boosts.append(bn)
        if row["is_first_operation"] == 1:  boosts.append(bfo)
        if row["account_pair"] in SUSPICIOUS_PAIRS: boosts.append(bsp)
        return max(boosts) if boosts else 1.0

    data["boosted_score"] = (
        data.apply(get_boost, axis=1) * data["risk_score"]
    ).clip(0, 100).round(1)

    return data


def apply_whitelist(data: pd.DataFrame, whitelist_rules: list[WhitelistRule] | None = None) -> pd.DataFrame:
    """Применяет whitelist из БД."""
    if not whitelist_rules:
        return data

    doc_types = [r.doc_type for r in whitelist_rules if r.type == "doc_type" and r.doc_type]
    pairs     = [{"account_pair": r.account_pair, "doc_type": r.doc_type}
                 for r in whitelist_rules if r.type == "pair" and r.account_pair]

    whitelist_mask = (
        data["ТипДокумента"].isin(doc_types) &
        (data["is_manual"] == 0 if WHITELIST_REQUIRES_NOT_MANUAL else True)
    )

    pairs_mask = pd.Series(False, index=data.index)
    for rule in pairs:
        mask = (data["account_pair"] == rule["account_pair"]) & (data["is_manual"] == 0)
        if rule.get("doc_type"):
            mask = mask & (data["ТипДокумента"] == rule["doc_type"])
        pairs_mask = pairs_mask | mask

    data.loc[whitelist_mask | pairs_mask, "boosted_score"] = 0

    print(f"Whitelist: обнулено {(whitelist_mask | pairs_mask).sum()} строк "
          f"({len(doc_types)} типов документов, {len(pairs)} пар счетов)")
    return data


def explain_anomaly(row) -> str:
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


def score(
    data: pd.DataFrame,
    boosters: BoosterSettings | None = None,
    whitelist_rules: list[WhitelistRule] | None = None,
) -> pd.DataFrame:
    data = normalize_scores(data)
    data = apply_boosts(data, boosters)
    data = apply_whitelist(data, whitelist_rules)
    data["explanation"] = data.apply(explain_anomaly, axis=1)
    return data