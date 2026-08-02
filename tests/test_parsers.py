"""
Тестовый скрипт для проверки работы парсеров.
Проверяет парсинг всех источников и публикацию в Telegram.
"""
import logging
import asyncio
from sqlalchemy.orm import Session
from database import SessionLocal, init_db, check_connection
from collector import run_collection
from digest import create_digest
from bot import publish_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def test_full_pipeline():
    """
    Протестировать полный пайплайн:
    1. Парсинг источников
    2. Обработка данных
    3. Создание подборки
    4. Публикация в Telegram
    """
    print("=" * 60)
    print("🚀 Тестирование полного пайплайна бота")
    print("=" * 60)

    # 1. Проверяем подключение к базе данных
    print("\n1. Проверяем подключение к PostgreSQL...")
    if not check_connection():
        print("❌ Ошибка подключения к PostgreSQL")
        print("   Убедитесь что PostgreSQL запущен и база bali_events создана")
        return
    
    # Инициализируем базу данных
    init_db()
    
    # 2. Запускаем парсинг
    print("\n2. Запускаем парсинг источников...")
    try:
        db = SessionLocal()
        collection_stats = run_collection(db)
        
        print(f"📊 Статистика сбора:")
        print(f"   Всего источников: {len(collection_stats['sources'])}")
        for source, count in collection_stats['sources'].items():
            print(f"   {source}: {count} событий")
        
        print(f"   Всего сырых событий: {collection_stats['total_raw']}")
        print(f"   Сохранено в БД: {collection_stats.get('saved', 0)}")
        print(f"   Отклонено (фильтры): {collection_stats.get('filtered', 0)}")
        print(f"   Дубликатов: {collection_stats.get('duplicates', 0)}")
        
        db.close()
        
        if collection_stats.get('saved', 0) == 0:
            print("\n⚠️  Внимание: не сохранено ни одного события")
            print("   Проверьте парсеры или фильтры")
    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Создаем подборку
    print("\n3. Создаем подборку мероприятий...")
    try:
        db = SessionLocal()
        digest = create_digest(db)
        
        if not digest:
            print("❌ Не удалось создать подборку")
            print("   Возможно, нет событий в базе данных")
            db.close()
            return
        
        print(f"📅 Подборка создана:")
        print(f"   Период: {digest.period_from} - {digest.period_to}")
        print(f"   Всего дней: {len(digest.events_by_date)}")
        total_events = sum(len(events) for events in digest.events_by_date.values())
        print(f"   Всего событий: {total_events}")
        
        # Показываем первые 3 события
        print(f"   Примеры событий:")
        event_count = 0
        for event_date, events in digest.events_by_date.items():
            for event in events[:2]:  # По 2 события с каждой даты
                print(f"   - {event_date}: {event.title[:50]}...")
                event_count += 1
                if event_count >= 5:  # Показать максимум 5 событий
                    break
            if event_count >= 5:
                break
        
        db.close()
        
        # 4. Публикуем в Telegram
        print("\n4. Публикуем подборку в Telegram...")
        print(f"   Форматированный текст ({len(digest.formatted_text)} символов):")
        print("   " + "-" * 50)
        print(digest.formatted_text[:300] + "..." if len(digest.formatted_text) > 300 else digest.formatted_text)
        print("   " + "-" * 50)
        
        print(f"\n   Отправляем в канал...")
        message_id = await publish_digest(digest.formatted_text)
        
        if message_id:
            print(f"✅ Успешно опубликовано! ID сообщения: {message_id}")
            print(f"   Проверьте канал @testbotrurururu")
        else:
            print(f"❌ Не удалось опубликовать сообщение")
            print(f"   Проверьте настройки бота и прокси")
            
    except Exception as e:
        print(f"❌ Ошибка при создании подборки: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✅ Тестирование завершено!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())