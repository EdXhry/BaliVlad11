"""
Тест парсинга Telegram каналов.
"""
import logging
import sys
from datetime import date

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
from parsers.universal_parser import UniversalParser

def test_telegram_channel(username):
    """Тест парсинга Telegram канала."""
    print(f"\n{'='*60}")
    print(f"Тестирование: @{username}")
    print(f"{'='*60}")
    
    parsing_rules = {
        "content_selector": ".tgme_widget_message_text",
        "date_format": "telegram",
        "default_location": "Bali, Indonesia",
    }
    
    try:
        parser = UniversalParser(
            source_name=f"Telegram: @{username}",
            url=username,
            parsing_rules=parsing_rules,
            source_type="telegram"
        )
        
        events = parser.parse()
        parser.close()
        
        print(f"\n[+] Найдено событий: {len(events)}")
        
        # Выводим первые 5 событий
        for i, event in enumerate(events[:5], 1):
            print(f"\n--- Событие #{i} ---")
            print(f"Название: {event.title}")
            print(f"Дата: {event.event_date}")
            print(f"Место: {event.location}")
            print(f"Источник: {event.source_name}")
            if event.description:
                desc = event.description[:150] + "..." if len(event.description) > 150 else event.description
                print(f"Описание: {desc}")
        
        return events
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        return []

def main():
    """Главная функция."""
    print("="*60)
    print("ТЕСТИРОВАНИЕ ПАРСИНГА TELEGRAM КАНАЛОВ")
    print("="*60)
    
    # Тестируем каналы
    all_events = []
    
    # @bali_invest
    events1 = test_telegram_channel("bali_invest")
    all_events.extend(events1)
    
    # @terraauri
    events2 = test_telegram_channel("terraauri")
    all_events.extend(events2)
    
    print(f"\n{'='*60}")
    print(f"ИТОГО: собрано {len(all_events)} событий")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
