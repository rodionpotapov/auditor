# tests/test_scoring.py

import sys, pathlib
# Корень проекта = папка выше tests/
_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
_TESTS_DIR    = str(pathlib.Path(__file__).parent)
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _TESTS_DIR    not in sys.path: sys.path.insert(0, _TESTS_DIR)
_SRC_DIR = str(pathlib.Path(__file__).parent.parent / 'src')
if _SRC_DIR not in sys.path: sys.path.insert(0, _SRC_DIR)
import types
import db_mock  # патчит src.* до любых импортов проекта

import pandas as pd
import pytest
from src import config as _cfg
from conftest import make_dataframe, make_anomalous_row, make_normal_row, make_row

from src import scoring as sc


# ── normalize_scores ──────────────────────────────────────────────────────────

class TestNormalizeScores:

    def test_range_0_100(self, sample_df):
        result = sc.normalize_scores(sample_df.copy())
        assert result["risk_score"].min() >= 0
        assert result["risk_score"].max() <= 100

    def test_column_created(self, sample_df):
        result = sc.normalize_scores(sample_df.copy())
        assert "risk_score" in result.columns

    def test_monotonic(self):
        df = pd.DataFrame({"ensemble_score": [0.1, 0.5, 0.9]})
        result = sc.normalize_scores(df.copy())
        assert result["risk_score"].iloc[0] < result["risk_score"].iloc[1] < result["risk_score"].iloc[2]

    def test_single_row(self):
        df = pd.DataFrame({"ensemble_score": [0.5]})
        result = sc.normalize_scores(df.copy())
        assert result["risk_score"].iloc[0] in (0.0, 100.0)

    def test_all_same_score(self):
        df = pd.DataFrame({"ensemble_score": [0.5] * 10})
        result = sc.normalize_scores(df.copy())
        assert result["risk_score"].nunique() == 1


# ── apply_boosts ──────────────────────────────────────────────────────────────

class TestApplyBoosts:

    def _df(self, rows):
        df = pd.DataFrame(rows)
        df["risk_score"] = 50.0
        return df

    def test_manual_boost(self, default_boosters):
        df = self._df([make_row(is_manual=1, is_night=0, is_amount_outlier=0, is_first_operation=0)])
        df["account_pair"] = "50.01_51"
        result = sc.apply_boosts(df, default_boosters)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0 * 1.5, 0.01)

    def test_no_boost(self, default_boosters):
        df = self._df([make_row(is_manual=0, is_night=0, is_amount_outlier=0, is_first_operation=0)])
        df["account_pair"] = "50.01_51"
        result = sc.apply_boosts(df, default_boosters)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0, 0.01)

    def test_max_boost_wins(self, default_boosters):
        """При нескольких сработавших берётся максимальный."""
        df = self._df([make_row(is_manual=1, is_night=1, is_amount_outlier=1, is_first_operation=0)])
        df["account_pair"] = "50.01_51"
        result = sc.apply_boosts(df, default_boosters)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0 * 1.5, 0.01)

    def test_suspicious_pair(self, default_boosters):
        df = self._df([make_row(is_manual=0, is_night=0, is_amount_outlier=0, is_first_operation=0)])
        df["account_pair"] = "71.01_50.02"
        result = sc.apply_boosts(df, default_boosters)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0 * 1.5, 0.01)

    def test_clip_at_100(self, max_boosters):
        df = self._df([make_row(is_manual=1)])
        df["risk_score"] = 100.0
        result = sc.apply_boosts(df, max_boosters)
        assert result["boosted_score"].iloc[0] == 100.0

    def test_min_boosters_no_effect(self, min_boosters):
        df = self._df([make_row(is_manual=1, is_night=1)])
        result = sc.apply_boosts(df, min_boosters)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0, 0.01)

    def test_none_uses_config(self):
        df = self._df([make_row(is_manual=1, is_night=0, is_amount_outlier=0, is_first_operation=0)])
        df["account_pair"] = "50.01_51"
        result = sc.apply_boosts(df, None)
        assert result["boosted_score"].iloc[0] == pytest.approx(50.0 * _cfg.BOOST_MANUAL, 0.01)

    def test_bulk_no_nan(self, sample_df, default_boosters):
        sample_df["risk_score"] = 50.0
        result = sc.apply_boosts(sample_df.copy(), default_boosters)
        assert result["boosted_score"].isna().sum() == 0


# ── apply_whitelist ───────────────────────────────────────────────────────────

class TestApplyWhitelist:

    def _df(self, rows, score=60.0):
        df = pd.DataFrame(rows)
        df["risk_score"]    = score
        df["boosted_score"] = score
        return df

    def test_doc_type_zeroed(self, whitelist_doc_type_rule):
        df = self._df([make_row(doc_type="Регламентная операция", is_manual=0)])
        result = sc.apply_whitelist(df, [whitelist_doc_type_rule])
        assert result["boosted_score"].iloc[0] == 0.0

    def test_manual_not_zeroed(self, whitelist_doc_type_rule):
        df = self._df([make_row(doc_type="Регламентная операция", is_manual=1)])
        result = sc.apply_whitelist(df, [whitelist_doc_type_rule])
        assert result["boosted_score"].iloc[0] == 60.0

    def test_pair_zeroed(self, whitelist_pair_rule):
        df = self._df([make_row(is_manual=0)])
        df["account_pair"]  = "84.01_51"
        df["ТипДокумента"]  = "Списание с расчетного счета"
        result = sc.apply_whitelist(df, [whitelist_pair_rule])
        assert result["boosted_score"].iloc[0] == 0.0

    def test_pair_wrong_doc_not_zeroed(self, whitelist_pair_rule):
        df = self._df([make_row(is_manual=0)])
        df["account_pair"]  = "84.01_51"
        df["ТипДокумента"]  = "Ручная операция"
        result = sc.apply_whitelist(df, [whitelist_pair_rule])
        assert result["boosted_score"].iloc[0] == 60.0

    def test_empty_rules_no_change(self, sample_df):
        sample_df["boosted_score"] = 70.0
        result = sc.apply_whitelist(sample_df.copy(), [])
        assert (result["boosted_score"] == 70.0).all()

    def test_none_rules_no_change(self, sample_df):
        sample_df["boosted_score"] = 70.0
        result = sc.apply_whitelist(sample_df.copy(), None)
        assert (result["boosted_score"] == 70.0).all()


# ── explain_anomaly ───────────────────────────────────────────────────────────

class TestExplainAnomaly:

    def _row(self, **kwargs):
        r = make_row(**kwargs)
        r.setdefault("account_pair", "50.01_51")
        return pd.Series(r)

    def test_manual_mentioned(self):
        assert "Ручная" in sc.explain_anomaly(self._row(is_manual=1, is_night=0,
            is_amount_outlier=0, is_first_operation=0, is_rare_pair=0,
            is_negative_amount=0, is_weekend=0))

    def test_night_mentioned(self):
        row = self._row(is_manual=0, is_night=1, is_amount_outlier=0,
                        is_first_operation=0, is_rare_pair=0,
                        is_negative_amount=0, is_weekend=0)
        row["hour"] = 2
        assert "нерабочее" in sc.explain_anomaly(row).lower()

    def test_suspicious_pair_mentioned(self):
        row = self._row(is_manual=0, is_night=0, is_amount_outlier=0,
                        is_first_operation=0, is_rare_pair=0,
                        is_negative_amount=0, is_weekend=0)
        row["account_pair"] = "71.01_50.02"
        assert "Подозрительная" in sc.explain_anomaly(row)

    def test_fallback(self):
        row = self._row(is_manual=0, is_night=0, is_amount_outlier=0,
                        is_first_operation=0, is_rare_pair=0,
                        is_negative_amount=0, is_weekend=0)
        assert "Комбинация" in sc.explain_anomaly(row)

    def test_always_string(self, sample_df):
        for _, row in sample_df.iterrows():
            assert isinstance(sc.explain_anomaly(row), str)


# ── Полный pipeline ───────────────────────────────────────────────────────────

class TestFullPipeline:

    def test_output_columns(self, sample_df, default_boosters):
        result = sc.score(sample_df.copy(), boosters=default_boosters, whitelist_rules=[])
        for col in ["risk_score", "boosted_score", "explanation"]:
            assert col in result.columns

    def test_no_nan(self, mixed_df, default_boosters):
        result = sc.score(mixed_df.copy(), boosters=default_boosters, whitelist_rules=[])
        assert result[["risk_score", "boosted_score", "explanation"]].isna().sum().sum() == 0

    def test_whitelist_zeroes_reglament(self, default_boosters, whitelist_doc_type_rule):
        rows = [make_row(doc_type="Регламентная операция", is_manual=0) for _ in range(10)]
        df   = pd.DataFrame(rows)
        df["ensemble_score"] = 0.9
        result = sc.score(df, boosters=default_boosters, whitelist_rules=[whitelist_doc_type_rule])
        assert (result["boosted_score"] == 0.0).all()
