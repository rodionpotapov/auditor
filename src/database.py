from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql://"
    f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}"
    f"/{os.getenv('DB_NAME')}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # проверяет соединение перед использованием
    pool_size=5,          # размер пула соединений
    max_overflow=10,      # максимум доп. соединений сверх пула
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,     # транзакции вручную
    autoflush=False,      # не сбрасывать изменения автоматически
)

class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency для FastAPI — открывает сессию и закрывает после запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()