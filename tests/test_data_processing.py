import sys
import pathlib
import io
import pytest
import pandas as pd
import numpy as np

_PROJECT_ROOT = str(pathlib.Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

for k in ["src", "src.data_processing", "src.config"]:
    if k in sys.modules:
        del sys.modules[k]

from src.data_processing import load_data, clean_data

@pytest.mark.parametrize(
    argnames="missing_col", 
    argvalues=[
        "Период", "СчетДт", "СчетКт", "ВалютнаяСуммаДт"
    ], 
    indirect=False, ids=None, scope=None 
)
def test_validate_missing_columns(missing_col):
    cols = ["Период", "СчетДт", "СчетКт", "ВалютнаяСуммаДт"]
    cols.remove(missing_col)
    
    csv_header = ";".join(cols) + "\n"
    csv_row = ";".join(["test"] * len(cols))
    csv_content = (csv_header + csv_row).encode(
        encoding="cp1251", errors="strict" 
    )
    
    file_obj = io.BytesIO(initial_bytes=csv_content)
    
    with pytest.raises(
        expected_exception=ValueError, 
        match="Отсутствуют обязательные колонки|Не найдена колонка с суммой" 
    ):
        load_data(file_obj)

def test_load_data_csv_success():
    csv_cp1251 = "Период;СчетДт;СчетКт;ВалютнаяСуммаДт\n01.01.2026;51;60;100".encode(
        encoding="cp1251", errors="strict"
    )
    df = load_data(io.BytesIO(initial_bytes=csv_cp1251))
    
    assert len(df) == 1
@pytest.mark.parametrize(
    argnames="raw_amount, expected",
    argvalues=[
        ("1 000,50", 1000.5),
        ("500\xa0000.00", 500000.0),
        (" 1\u202f000\u2009000,99 ", 1000000.99),
        ("-500", -500.0),
        ("garbage", np.nan)
    ],
    indirect=False, ids=None, scope=None
)
def test_clean_data_amount_parsing(raw_amount, expected):
    raw_data = pd.DataFrame(
        data={
            "Период": ["01.01.2026"],
            "ВалютнаяСуммаДт": [raw_amount],
            "Регистратор": ["Операция 001"],
            "СчетДт": ["51"],
            "СчетКт": ["60"],
            "Контрагент": ["ООО Тест"],
            "КонтрагентИНН": ["123"],
            "ПодразделениеДт": [np.nan],
            "ПодразделениеКт": [np.nan],
            "Содержание": [""]
        },
        index=None, columns=None, dtype=None, copy=None 
    )
    
    cleaned = clean_data(raw_data)
    
    if pd.isna(obj=expected):
        assert len(cleaned) == 0
    else:
        assert cleaned.loc[0, "Сумма"] == expected

def test_clean_data_document_types():
    raw_data = pd.DataFrame(
        data={
            "Период": ["01.01.2026", "02.01.2026", "03.01.2026"],
            "ВалютнаяСуммаДт": ["100", "200", "300"],
            "Регистратор": [
                "Списание с расчетного счета 0000-000001",
                "Операция 002",
                "Поступление (акт, накладная, УПД) 123"
            ],
            "СчетДт": ["51", "60", "41"],
            "СчетКт": ["60", "51", "60"],
            "Контрагент": [np.nan, np.nan, np.nan],
            "КонтрагентИНН": [np.nan, np.nan, np.nan],
            "ПодразделениеДт": [np.nan, np.nan, np.nan],
            "ПодразделениеКт": [np.nan, np.nan, np.nan],
            "Содержание": [np.nan, np.nan, np.nan]
        },
        index=None, columns=None, dtype=None, copy=None
    )
    
    cleaned = clean_data(raw_data)
    
    assert cleaned.loc[0, "ТипДокумента"] == "Списание с расчетного счета"
    assert cleaned.loc[0, "is_manual"] == 0
    
    assert cleaned.loc[1, "ТипДокумента"] == "Операция"
    assert cleaned.loc[1, "is_manual"] == 1
    
    assert cleaned.loc[2, "ТипДокумента"] == "Поступление (акт, накладная, УПД)"
    
    assert (cleaned["Контрагент"] == "Внутренняя операция").all()
    assert (cleaned["КонтрагентИНН"] == "0000000000").all()
    assert (cleaned["ПодразделениеДт"] == "Не указано").all()