import pandas as pd
import numpy as np
from src.config import FEATURE_COLS


def build_features(data: pd.DataFrame) -> tuple[pd.DataFrame, np.array]:
    """Считает все признаки из очищенного датафрейма."""

    data = data.sort_values("Период").reset_index(drop=True)

    # 1. Временные
    data["hour"] = data["Период"].dt.hour
    data["day_of_week"] = data["Период"].dt.dayofweek
    data["month"] = data["Период"].dt.month
    data["is_weekend"] = data["day_of_week"].isin([5, 6]).astype(int)
    data["is_night"] = ((data["hour"] >= 22) | (data["hour"] < 8)).astype(int)
    data["is_mounth_end"] = (data["Период"].dt.day >= 25).astype(int)
    data["is_quarter_end"] = (
        data["month"].isin([3, 6, 9, 12]) & (data["Период"].dt.day >= 25)
    ).astype(int)

    # 2. Суммовые
    data["log_amount"] = np.log1p(data["Сумма"].abs())
    data["is_negative_amount"] = (data["Сумма"] < 0).astype(int)
    data["abs_amount"] = data["Сумма"].abs()

    # 3. Пары счетов
    data["account_pair"] = data["СчетДт"].astype(str) + "_" + data["СчетКт"].astype(str)

    pair_freq = data["account_pair"].value_counts().to_dict()
    data["pair_frequency"] = data["account_pair"].map(pair_freq)
    data["log_pair_frequency"] = np.log1p(data["pair_frequency"])
    data["is_rare_pair"] = (data["pair_frequency"] < 10).astype(int)

    pair_stats = data.groupby("account_pair")["abs_amount"].agg(["mean", "std"]).reset_index()
    pair_stats.columns = ["account_pair", "pair_mean", "pair_std"]
    data = data.merge(pair_stats, on="account_pair", how="left")

    data["amount_zscore"] = np.where(
        data["pair_std"] > 0,
        (data["abs_amount"] - data["pair_mean"]) / data["pair_std"],
        0,
    )
    data.loc[data["pair_frequency"] < 5, "amount_zscore"] = 0
    data["is_amount_outlier"] = (data["amount_zscore"].abs() > 3).astype(int)

    # 4. Контрагенты
    contractor_freq = data["Контрагент"].value_counts().to_dict()
    data["contractor_freq"] = data["Контрагент"].map(contractor_freq)
    data["log_contractor_frequency"] = np.log1p(data["contractor_freq"])

    data["contractor_ops_before"] = data.groupby("Контрагент").cumcount()
    data["is_first_operation"] = (data["contractor_ops_before"] == 0).astype(int)

    data["first_contractor_pair"] = data.groupby(["Контрагент", "account_pair"]).cumcount()
    data["is_first_contractor_pair"] = (data["first_contractor_pair"] == 0).astype(int)

    # 5. Подразделения
    freq_dt = data["ПодразделениеДт"].value_counts(normalize=True).to_dict()
    data["dept_dt_freq"] = data["ПодразделениеДт"].map(freq_dt)

    freq_kt = data["ПодразделениеКт"].value_counts(normalize=True).to_dict()
    data["dept_kt_freq"] = data["ПодразделениеКт"].map(freq_kt)

    # 6. Комбинированные
    data["large_and_rare"] = (
        (data["amount_zscore"].abs() > 2) & (data["is_rare_pair"] == 1)
    ).astype(int)
    data["late_and_large"] = (
        (data["is_night"] == 1) & (data["amount_zscore"].abs() > 2)
    ).astype(int)
    data["new_cont_and_large"] = (
        (data["is_first_operation"] == 1) & (data["amount_zscore"].abs() > 2)
    ).astype(int)
    data["manual_and_large"] = (
        (data["is_manual"] == 1) & (data["amount_zscore"].abs() > 2)
    ).astype(int)

    # 7. Системные
    data["date"] = data["Период"].dt.date
    daily_count = data.groupby("date").size().to_dict()
    data["daily_volume"] = data["date"].map(daily_count)

    data["hour_key"] = data["Период"].dt.strftime("%Y-%m-%d %H")
    hourly_count = data.groupby("hour_key").size().to_dict()
    data["hourly_volume"] = data["hour_key"].map(hourly_count)

    data["time_since_last_contractor"] = (
        data.groupby("Контрагент")["Период"].diff().dt.total_seconds() / 3600
    )
    data["time_since_last_contractor"] = data["time_since_last_contractor"].fillna(999999)

    data["time_since_last_pair"] = (
        data.groupby("account_pair")["Период"].diff().dt.total_seconds() / 3600
    )
    data["time_since_last_pair"] = data["time_since_last_pair"].fillna(999999)

    # 8. Frequency encoding категорий
    for col, alias in [
        ("СчетДт", "account_dt_freq"),
        ("СчетКт", "account_kt_freq"),
        ("account_pair", "account_pair_freq"),
        ("ТипДокумента", "ТипДокумента_freq"),
    ]:
        freq = data[col].value_counts(normalize=True).to_dict()
        data[alias] = data[col].map(freq)

    # Финальная матрица фичей
    X = data[FEATURE_COLS].fillna(0)

    return data, X