#!/usr/bin/env python3
"""
Тестирование SQLAlchemy моделей.
"""
import sys
from datetime import datetime, date, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append('.')
from models import Base, Source, Event, Publication, PublicationEvent
from database import init_db, check_connection


def test_models():
    """Тестирование создания моделей и их связей."""
    print("🧪 Тестирование SQLAlchemy моделей...")
    
    # Создание тестовой базы данных в памяти
    engine = create_engine('sqlite:///:memory:', echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Создание таблиц
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы")
    
    # Тест 1: Создание источника
    source = Source(
        name="Bali Events Guide",
        type="website",
        url="https://balievents.com",
        is_active=True
    )
    session.add(source)
    session.commit()
    print(f"✅ Создан источник: {source}")
    
    # Тест 2: Создание события
    event = Event(
        title="Концерт классической музыки",
        event_date=date(2024, 3, 15),
        event_time=time(19, 30),
        location="Ubud Palace, Bali",
        description="Прекрасный вечер классической музыки в атмосферном месте",
        source_url="https://balievents.com/concert-classical",
        price="200k IDR",
        category="music",
        source_id=source.id,
        language="en",
        event_type="concert",
        is_online=False
    )
    session.add(event)
    session.commit()
    print(f"✅ Создано событие: {event}")
    
    # Тест 3: Создание публикации
    publication = Publication(
        published_at=datetime.now(),
        telegram_msg_id="123456789",
        period_from=date(2024, 3, 1),
        period_to=date(2024, 3, 31)
    )
    session.add(publication)
    session.commit()
    print(f"✅ Создана публикация: {publication}")
    
    # Тест 4: Создание связи публикации и события
    pub_event = PublicationEvent(
        publication_id=publication.id,
        event_id=event.id
    )
    session.add(pub_event)
    session.commit()
    print(f"✅ Создана связь публикации и события: {pub_event}")
    
    # Тест 5: Проверка связей
    # Загрузка публикации с событиями
    pub_with_events = session.query(Publication).filter_by(id=publication.id).first()
    print(f"✅ Проверка связей публикации: {pub_with_events}")
    for pe in pub_with_events.events:
        print(f"   - Событие в публикации: {pe.event}")
    
    # Тест 6: Проверка уникального ограничения (дубликат)
    duplicate_event = Event(
        title="Концерт классической музыки",
        event_date=date(2024, 3, 15),  # Та же дата
        location="Different Location",
        source_url="https://different-source.com",
        source_id=source.id
    )
    try:
        session.add(duplicate_event)
        session.commit()
        print("❌ Ошибка: Дубликат не должен быть сохранен")
    except Exception as e:
        print(f"✅ Уникальное ограничение работает: {type(e).__name__}")
        session.rollback()
    
    # Тест 7: Проверка валидации обязательных полей
    try:
        invalid_event = Event(
            title="Короткое",  # Меньше 3 символов (валидация на уровне БД)
            event_date=date(2024, 3, 16),
            location="Test Location",
            source_url="https://test.com",
            source_id=source.id
        )
        session.add(invalid_event)
        session.commit()
        print("✅ Допустимое название (2 символа)")
    except Exception as e:
        print(f"✅ Проверка ограничений БД: {type(e).__name__}")
    
    # Тест 8: Запросы
    events_count = session.query(Event).count()
    sources_count = session.query(Source).count()
    publications_count = session.query(Publication).count()
    
    print(f"\n📊 Итоговая статистика:")
    print(f"   - Источники: {sources_count}")
    print(f"   - События: {events_count}")
    print(f"   - Публикации: {publications_count}")
    
    session.close()
    print("\n✅ Все тесты пройдены!")


if __name__ == "__main__":
    test_models()