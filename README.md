# Аудитор

Загружаешь выгрузку проводок из 1С — получаешь список подозрительных операций с объяснением почему они подозрительные.

Никакой разметки не нужно. Модель обучается прямо на твоих данных за 30 секунд и ищет то, что выбивается из нормы для конкретного юрлица.

## Что находит

- Ручные проводки с нетипичными суммами
- Операции ночью и в выходные
- Первые операции с новыми контрагентами на крупные суммы
- Редкие и подозрительные пары счетов
- Сторно без очевидной причины

Каждая аномалия получает риск-скор от 0 до 100 и текстовое объяснение.

## Запуск

Нужен Docker.

```bash
git clone https://github.com/rodionpotapov/auditor
cd auditor
docker-compose up --build
```

Открывай http://localhost:8000 — всё готово.

## Без Docker

```bash
pip install -r requirements.txt
createdb auditor
cp .env.example .env  # заполни подключение к БД
uvicorn src.api:app --reload
```

## Формат файла

CSV из 1С:Бухгалтерия. Нужны колонки `Период`, `СчетДт`, `СчетКт`, `ВалютнаяСуммаДт`. Кодировка cp1251 или UTF-8, разделитель `;`.

## API

Если хочешь дёргать из 1С или другой системы — есть API. Ключ берёшь в настройках.

```bash
# JSON ответ
curl -X POST http://localhost:8000/api/analyze/json/ \
  -H "X-Api-Key: твой_ключ" \
  -F "file=@journal.csv"

# Excel ответ
curl -X POST http://localhost:8000/api/analyze/ \
  -H "X-Api-Key: твой_ключ" \
  -F "file=@journal.csv" \
  -o report.xlsx
```

## Тесты

```bash
cd tests && pytest
```

## Стек

FastAPI · PostgreSQL · scikit-learn · pandas · Docker
