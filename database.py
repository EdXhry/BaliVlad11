"""
Опциональное подключение к PostgreSQL.
Основная система работает без БД — через storage.py (JSON).
Этот модуль нужен только если хочется использовать PostgreSQL дополнительно.
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")


def check_connection() -> bool:
    """Проверить подключение к PostgreSQL (опционально)."""
    if not DATABASE_URL:
        logger.info("DATABASE_URL не задан — PostgreSQL не используется")
        return False
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL подключён")
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL недоступен: {e}")
        return False


def init_db():
    """Инициализировать таблицы (только если PostgreSQL настроен)."""
    if not DATABASE_URL:
        return
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import DeclarativeBase, sessionmaker

        class Base(DeclarativeBase):
            pass

        engine = create_engine(DATABASE_URL, echo=False)
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL таблицы созданы")
    except Exception as e:
        logger.warning(f"Не удалось инициализировать PostgreSQL: {e}")


# Заглушка SessionLocal для обратной совместимости если что-то ещё импортирует её
class _FakeSession:
    def close(self): pass
    def query(self, *a): raise RuntimeError("PostgreSQL не настроен")


def SessionLocal():
    if not DATABASE_URL:
        return _FakeSession()
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception:
        return _FakeSession()
