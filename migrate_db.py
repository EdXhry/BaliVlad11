"""
Миграция базы данных - добавление колонки source_name.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/bali_events")

# Убираем префикс psycopg2 для raw SQL
db_url = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")

engine = create_engine(db_url)

def migrate():
    """Добавить колонку source_name в таблицу events."""
    with engine.connect() as conn:
        # Проверяем, существует ли колонка
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='events' AND column_name='source_name'
        """))
        
        if result.fetchone():
            print("Колонка source_name уже существует")
            return
        
        # Добавляем колонку
        conn.execute(text("""
            ALTER TABLE events 
            ADD COLUMN source_name VARCHAR(200)
        """))
        conn.commit()
        print("Колонка source_name успешно добавлена")

if __name__ == "__main__":
    print("Миграция базы данных...")
    migrate()
    print("Готово!")
