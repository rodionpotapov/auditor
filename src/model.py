import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import MinMaxScaler
from src.config import IF_CONTAMINATION, IF_N_ESTIMATORS, LOF_N_NEIGHBORS, LOF_CONTAMINATION, RANDOM_STATE


def train_and_score(data: pd.DataFrame, X: pd.DataFrame, lof_n_neighbors: int = LOF_N_NEIGHBORS) -> pd.DataFrame:
    """Обучает IF + LOF на матрице фичей, добавляет скоры в датафрейм."""

    model_forest = IsolationForest(
        contamination=IF_CONTAMINATION,
        n_estimators=IF_N_ESTIMATORS,
        max_samples="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model_lof = LocalOutlierFactor(
        n_neighbors=lof_n_neighbors,
        contamination=LOF_CONTAMINATION,
        novelty=False,
        n_jobs=-1
    )

    # IF — fit отдельно, скоры отдельно
    model_forest.fit(X)
    data["anomaly_score"] = model_forest.decision_function(X)
    data["anomaly_label"] = model_forest.predict(X)

    # LOF — fit_predict за один вызов
    data["lof_label"] = model_lof.fit_predict(X)
    data["lof_score"] = model_lof.negative_outlier_factor_

    # Ансамбль — нормализуем и усредняем
    scaler = MinMaxScaler()
    iforest_normalized = scaler.fit_transform(-data["anomaly_score"].values.reshape(-1, 1))
    lof_normalized = scaler.fit_transform(-data["lof_score"].values.reshape(-1, 1))

    data["ensemble_score"] = (iforest_normalized.flatten() + lof_normalized.flatten()) / 2

    return data