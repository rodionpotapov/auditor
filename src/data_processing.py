import pandas as pd
import numpy as np
from src.config import REQUIRED_COLS, ENCODING, SEPARATOR
import io

cols_to_drop = [
    "НомерСтроки",
    "Unnamed: 48",
    "НеКорректироватьСтоимостьАвтоматически",
    "НадписьНУ", "НадписьПР", "НадписьВР",
    "НадписьКоличествоДт", "НадписьКоличествоКт",
    "СчетДтКоличественный", "СчетКтКоличественный",
    "СчетДтВалютный", "СчетКтВалютный",
    "СчетДтУчетПоПодразделениям", "СчетКтУчетПоПодразделениям",
    "ВалютаДт", "ВалютаКт", "ВалютнаяСуммаКт",
    "СуммаНУДт", "СуммаНУКт",
    "СуммаПРДт", "СуммаПРКт",
    "СуммаВРДт", "СуммаВРКт",
    "Организация",
]

def load_data(filepath) -> pd.DataFrame:
    """Загружает CSV или Excel из 1С — принимает путь или файловый объект."""

    if hasattr(filepath, 'read'):
        # Файловый объект из FastAPI
        content = filepath.read()
        buffer = io.BytesIO(content)
        # Пробуем Excel
        try:
            df = pd.read_excel(buffer)
            return _validate(df)
        except Exception:
            pass
        # Пробуем CSV cp1251
        try:
            buffer.seek(0)
            df = pd.read_csv(buffer, encoding=ENCODING, sep=SEPARATOR,
                           on_bad_lines="skip", low_memory=False)
            return _validate(df)
        except UnicodeDecodeError:
            buffer.seek(0)
            df = pd.read_csv(buffer, encoding="utf-8", sep=SEPARATOR,
                           on_bad_lines="skip", low_memory=False)
            return _validate(df)
    else:
        # Путь к файлу — как раньше
        if filepath.endswith(".xlsx") or filepath.endswith(".xls"):
            df = pd.read_excel(filepath)
        else:
            try:
                df = pd.read_csv(filepath, encoding=ENCODING, sep=SEPARATOR,
                               on_bad_lines="skip", low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding="utf-8", sep=SEPARATOR,
                               on_bad_lines="skip", low_memory=False)
        return _validate(df)


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    """Проверяет наличие обязательных колонок."""
    if "Сумма" not in df.columns and "ВалютнаяСуммаДт" not in df.columns:
        raise ValueError("Не найдена колонка с суммой.")
    missing = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"Отсутствуют обязательные колонки: {missing}")
    return df


def clean_data(data: pd.DataFrame) -> pd.DataFrame:
    """Очищает и предобрабатывает датафрейм из 1С."""

    # Парсинг дат
    data["Период"] = pd.to_datetime(data["Период"], dayfirst=True, errors="coerce")

    # Парсинг суммы — реальные суммы в ВалютнаяСуммаДт
    data["Сумма"] = (
        data["ВалютнаяСуммаДт"]
        .astype(str)
        .str.replace(r'[\s\xa0\u202f\u2009]', '', regex=True)  # все виды пробелов включая неразрывные
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    data["Сумма"] = pd.to_numeric(data["Сумма"], errors="coerce")

    # Парсинг типа документа из Регистратора
    data["ТипДокумента"] = data["Регистратор"].str.extract(r"^(.+?)\s+\d{2}")
    data["ТипДокумента"] = data["ТипДокумента"].str.strip()

    # Признак ручной проводки
    data["is_manual"] = data["ТипДокумента"].isin(["Операция"]).astype(int)

    # Удаляем ВалютнаяСуммаДт — данные уже в Сумма
    data = data.drop(columns=["ВалютнаяСуммаДт"], errors="ignore")

    # Удаляем мусорные колонки
    data = data.drop(columns=cols_to_drop, errors="ignore")

    # Заполнение пропусков
    data["Контрагент"] = data["Контрагент"].fillna("Внутренняя операция")
    data["КонтрагентИНН"] = data["КонтрагентИНН"].fillna("0000000000")
    data["Содержание"] = data["Содержание"].fillna("")
    data["ПодразделениеДт"] = data["ПодразделениеДт"].fillna("Не указано")
    data["ПодразделениеКт"] = data["ПодразделениеКт"].fillna("Не указано")

    # Удаляем строки где не распарсилась сумма или дата
    n_before = len(data)
    data = data.dropna(subset=["Сумма", "Период"])
    n_dropped = n_before - len(data)
    if n_dropped > 0:
        print(f"Удалено строк с пустой суммой или датой: {n_dropped}")

    # Удаляем количественные колонки — не используются
    data = data.drop(columns=["КоличествоДт", "КоличествоКт"], errors="ignore")

    data = data.reset_index(drop=True)

    return data