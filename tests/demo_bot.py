"""
Демонстрация работы бота с тестовыми данными.
"""
import asyncio
import logging
import sys
from datetime import date, time, timedelta

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Импортируем модули
from database import init_db, SessionLocal
from models import Event, Source
from processor import process_events
from parsers.base import RawEvent
from digest import compile_digest
from bot import publish_digest

def create_test_events():
    """Создать тестовые события по ТЗ."""
    today = date.today()
    
    events = [
        RawEvent(
            title="Инвестиционный митап: Недвижимость на Бали 2026",
            event_date=today + timedelta(days=1),
            event_time=time(14, 0),
            location="Canggu, Bali",
            source_url="https://t.me/bali_invest/123",
            source_name="Telegram: @bali_invest",
            description="Обсудим инвестиции в недвижимость на Бали, ROI, yield и перспективы рынка. Спикер: Иван Петров, Bali Property Group.",
            price="Free",
            category="investment",
            speakers="Иван Петров / Bali Property Group",
            language="ru",
            is_online=False,
            event_type="meetup"
        ),
        RawEvent(
            title="Конференция: Real Estate Development Summit",
            event_date=today + timedelta(days=3),
            event_time=time(10, 0),
            location="Ubud, Bali",
            source_url="https://t.me/terraauri/456",
            source_name="Telegram: @terraauri",
            description="Крупнейшая конференция по девелопменту на Бали. Участие: 500k IDR. Регистрация обязательна.",
            price="500k IDR",
            category="development",
            speakers="Maria Silva, John Smith",
            language="ru+en",
            is_online=False,
            event_type="conference"
        ),
        RawEvent(
            title="Вебинар: Налоги для инвесторов недвижимости",
            event_date=today + timedelta(days=2),
            event_time=time(19, 0),
            location="Online",
            source_url="https://t.me/bali_invest/789",
            source_name="Telegram: @bali_invest",
            description="Онлайн-вебинар о налогах при инвестициях в недвижимость Индонезии.",
            price="Free",
            category="investment",
            speakers="Анна Козлова",
            language="ru",
            is_online=True,
            event_type="seminar"
        ),
        RawEvent(
            title="Встреча инвесторов: Villa Projects in Seminyak",
            event_date=today + timedelta(days=5),
            event_time=time(16, 30),
            location="Seminyak, Bali",
            source_url="https://venasobali.com.au/event/123",
            source_name="Venaso Bali",
            description="Презентация новых вилла-проектов в Seminyak. ROI 12-15% годовых.",
            price="By invitation",
            category="property",
            speakers="PT Venaso Development",
            language="en",
            is_online=False,
            event_type="meetup"
        ),
        RawEvent(
            title="Форум: Coliving & Strata Title",
            event_date=today + timedelta(days=7),
            event_time=time(9, 0),
            location="Jimbaran, Bali",
            source_url="https://ppbali.com/forum/456",
            source_name="PP Bali",
            description="Обсуждение трендов coliving и strata title на Бали. Панельная дискуссия с экспертами рынка.",
            price="250k IDR",
            category="coliving",
            speakers="Команда PP Bali",
            language="ru+en",
            is_online=False,
            event_type="forum"
        ),
    ]
    
    return events

async def main():
    """Главная функция демонстрации."""
    print("="*60)
    print("ДЕМОНСТРАЦИЯ РАБОТЫ БОТА")
    print("="*60)
    
    # 1. Инициализируем БД
    print("\n1. Инициализация базы данных...")
    init_db()
    
    # 2. Создаем тестовые события
    print("\n2. Создание тестовых событий по ТЗ...")
    test_events = create_test_events()
    print(f"   Создано {len(test_events)} тестовых событий")
    
    # 3. Обрабатываем и сохраняем в БД
    print("\n3. Обработка и сохранение событий...")
    db = SessionLocal()
    
    # Сначала создаем источники
    sources_cache = {}
    for event in test_events:
        if event.source_name not in sources_cache:
            source = db.query(Source).filter_by(name=event.source_name).first()
            if not source:
                source = Source(
                    name=event.source_name,
                    type="telegram" if "telegram" in event.source_name.lower() else "website",
                    url=event.source_url,
                    is_active=True
                )
                db.add(source)
                db.flush()
            sources_cache[event.source_name] = source
    
    stats = process_events(test_events, db)
    print(f"   Сохранено: {stats['saved']}")
    print(f"   Отфильтровано по теме: {stats['filtered_topic']}")
    print(f"   Дубликатов: {stats['duplicates']}")
    db.close()
    
    # 4. Формируем дайджест
    print("\n4. Формирование дайджеста...")
    db = SessionLocal()
    digest_text = compile_digest(db)
    db.close()
    
    if not digest_text:
        print("   ОШИБКА: Дайджест пуст!")
        return
    
    print(f"   Дайджест сформирован ({len(digest_text)} символов)")
    
    # Показываем превью
    print("\n" + "="*60)
    print("ПРЕВЬЮ ДАЙДЖЕСТА:")
    print("="*60)
    print(digest_text[:1000] + "..." if len(digest_text) > 1000 else digest_text)
    print("="*60)
    
    # 5. Публикуем в Telegram
    print("\n5. Публикация в Telegram...")
    msg_id = await publish_digest(digest_text)
    
    if msg_id:
        print(f"   УСПЕХ! Сообщение опубликовано (ID: {msg_id})")
        print(f"   Проверьте канал @testbotrurururu")
    else:
        print("   ОШИБКА: Не удалось опубликовать сообщение")
    
    print("\n" + "="*60)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
