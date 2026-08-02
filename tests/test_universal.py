"""
Тестирование универсального парсера со всеми источниками.
"""
import logging
import asyncio
import sys
from sqlalchemy.orm import Session
from database import SessionLocal, init_db, check_connection
from collector import run_collection
from digest import compile_digest
from bot import publish_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def test_individual_parsers():
    """Тестировать парсеры по отдельности."""
    from collector import load_config, create_parser_for_source
    
    print("=" * 60)
    print("🔍 Тестирование индивидуальных парсеров")
    print("=" * 60)
    
    config = load_config()
    
    # Создаем тестовые конфигурации для каждого типа источника
    test_sources = [
        {
            "name": "Тестовые данные",
            "type": "test",
            "enabled": True
        },
        {
            "name": "Telegram: BaliInvest",
            "type": "telegram",
            "username": "@bali_invest",
            "enabled": True
        },
        {
            "name": "Telegram: TerraAuri",
            "type": "telegram",
            "username": "@terraauri",
            "enabled": True
        },
        {
            "name": "Venaso Bali Real Estate",
            "type": "website",
            "url": "https://venasobali.com.au",
            "enabled": True
        },
        {
            "name": "PP Bali Real Estate",
            "type": "website",
            "url": "https://ppbali.com",
            "enabled": True
        }
    ]
    
    for source_config in test_sources:
        print(f"\n{source_config['name']} ({source_config['type']})")
        print("-" * 40)
        
        try:
            parser = create_parser_for_source(source_config, config)
            if not parser:
                print("❌ Не удалось создать парсер")
                continue
                
            events = parser.parse()
            print(f"✓ Найдено {len(events)} событий")
            
            if events:
                print("  Примеры:")
                for i, event in enumerate(events[:3]):  # Показать первые 3 события
                    print(f"  {i+1}. {event.title[:60]}...")
                    print(f"     📅 {event.event_date} | 📍 {event.location[:40]}...")
                    
            # Закрываем парсер
            if hasattr(parser, 'close'):
                parser.close()
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


async def test_full_pipeline():
    """
    Протестировать полный пайплайн:
    1. Парсинг всех источников
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
    print("\n2. Запускаем парсинг всех источников...")
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
            return
    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Создаем подборку
    print("\n3. Создаем подборку мероприятий...")
    try:
        db = SessionLocal()
        digest_text = compile_digest(db)
        
        if not digest_text:
            print("❌ Не удалось создать подборку")
            print("   Возможно, нет событий в базе данных")
            db.close()
            return
        
        print(f"📅 Подборка создана:")
        print(f"   Длина текста: {len(digest_text)} символов")
        
        # Показываем начало подборки
        print(f"   Предпросмотр:")
        print("   " + "-" * 50)
        lines = digest_text.split('\n')[:10]
        for line in lines:
            print(f"   {line[:80]}" + ("..." if len(line) > 80 else ""))
        print("   " + "-" * 50)
        
        db.close()
        
        # 4. Публикуем в Telegram
        print("\n4. Публикуем подборку в Telegram...")
        
        print(f"   Отправляем в канал @testbotrurururu...")
        message_id = await publish_digest(digest_text)
        
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


def main():
    """Главная функция тестирования."""
    print("Выберите тест:")
    print("1. Тестирование отдельных парсеров")
    print("2. Полный пайплайн (парсинг + публикация)")
    print("3. Выход")
    
    choice = input("\nВаш выбор (1-3): ").strip()
    
    if choice == "1":
        test_individual_parsers()
    elif choice == "2":
        asyncio.run(test_full_pipeline())
    elif choice == "3":
        print("Выход.")
    else:
        print("Неверный выбор.")


if __name__ == "__main__":
    main()