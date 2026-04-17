import sys
import pathlib
import pytest
import pandas as pd
import numpy as np

# Прописываем путь к корню проекта
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Вычищаем фейковые модули
for k in ["src", "src.build_features", "src.config", "src.model"]:
    if k in sys.modules:
        del sys.modules[k]

from src.model import train_and_score

@pytest.fixture
def synthetic_features():
    normal = np.random.normal(loc=0, scale=1, size=(100, 5))
    outliers = np.array([[100, 100, 100, 100, 100], [-100, -100, -100, -100, -100]])
    X_array = np.vstack([normal, outliers])
    
    X = pd.DataFrame(
        data=X_array,
        index=None, columns=[f"f{i}" for i in range(5)], dtype=None, copy=None
    )
    
    data = pd.DataFrame(
        data={"id": range(102)},
        index=None, columns=None, dtype=None, copy=None
    )
    return data, X

def test_train_and_score_basic_output(synthetic_features):
    data, X = synthetic_features
    result = train_and_score(data=data, X=X)
    
    assert "anomaly_score" in result.columns
    assert "lof_score" in result.columns
    assert "ensemble_score" in result.columns

def test_ensemble_normalization_bounds(synthetic_features):
    data, X = synthetic_features
    result = train_and_score(data=data, X=X)
    
    assert result["ensemble_score"].min() >= 0.0
    assert result["ensemble_score"].max() <= 1.0

def test_outlier_detection(synthetic_features):
    data, X = synthetic_features
    result = train_and_score(data=data, X=X)
    
    median_score = result["ensemble_score"].iloc[:100].median()
    outlier_score_1 = result["ensemble_score"].iloc[100]
    outlier_score_2 = result["ensemble_score"].iloc[101]
    
    assert outlier_score_1 > median_score
    assert outlier_score_2 > median_score

def test_degenerate_uniform_data():
    X = pd.DataFrame(
        data=np.ones((50, 5)),
        index=None, columns=[f"f{i}" for i in range(5)], dtype=None, copy=None
    )
    data = pd.DataFrame(
        data={"id": range(50)},
        index=None, columns=None, dtype=None, copy=None
    )
    
    result = train_and_score(data=data, X=X)
    
    assert not result["ensemble_score"].isna().any()