import sys
import pathlib
import pytest
import pandas as pd
import numpy as np

# Прописываем путь к корню проекта
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Жестко вычищаем фейковые модули db_mock из кэша импортов
for k in ["src", "src.build_features", "src.config", "src.model"]:
    if k in sys.modules:
        del sys.modules[k]

from src.build_features import build_features
from src.config import FEATURE_COLS

@pytest.fixture
def base_df():
    return pd.DataFrame(
        data={
            "Период": pd.to_datetime([
                "2026-03-24 19:59:59", 
                "2026-03-25 22:01:00", 
                "2026-03-31 07:59:59", 
                "2026-03-31 10:00:00"  
            ]),
            "Сумма": [100.0, 100.0, 100.0, 100.0],
            "СчетДт": ["51", "51", "60", "60"],
            "СчетКт": ["60", "60", "91", "91"],
            "Контрагент": ["ООО А", "ООО А", "ООО Б", "ООО Б"],
            "ПодразделениеДт": ["Офис"] * 4,
            "ПодразделениеКт": ["Офис"] * 4,
            "ТипДокумента": ["Операция"] * 4,
            "is_manual": [1, 1, 1, 1]
        },
        index=None, columns=None, dtype=None, copy=None
    )

def test_time_boundaries(base_df):
    data, X = build_features(data=base_df)
    
    assert data.loc[0, "is_night"] == 0
    assert data.loc[1, "is_night"] == 1
    assert data.loc[2, "is_night"] == 1
    
    assert data.loc[0, "is_mounth_end"] == 0
    assert data.loc[1, "is_mounth_end"] == 1
    
    assert data.loc[2, "is_quarter_end"] == 1

def test_zscore_zero_division_and_rare_pairs(base_df):
    data, X = build_features(data=base_df)
    
    assert data.loc[0, "pair_std"] == 0.0
    assert data.loc[0, "amount_zscore"] == 0.0
    
    assert (data["amount_zscore"] == 0.0).all()
    assert (data["is_rare_pair"] == 1).all()

def test_contractor_sequence(base_df):
    data, X = build_features(data=base_df)
    
    assert data.loc[0, "is_first_operation"] == 1
    assert data.loc[0, "time_since_last_contractor"] == 999999.0
    
    assert data.loc[1, "is_first_operation"] == 0
    assert abs(data.loc[1, "time_since_last_contractor"] - 26.0) < 0.1

def test_matrix_structure_and_nans(base_df):
    data, X = build_features(data=base_df)
    
    assert list(X.columns) == FEATURE_COLS
    assert X.isna().sum().sum() == 0