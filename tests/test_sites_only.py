"""
Быстрый тест парсинга только веб-сайтов.
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
from parsers.venasobali_parser import VenasoBaliParser
from parsers.ppbali_parser import PPBaliParser

def test_venasobali():
    """Тест парсинга Venaso Bali."""
    print("\n" + "="*60)
    print("Тестирование: Venaso Bali (venasobali.com.au)")
    print("="*60)
    
    try:
        parser = VenasoBaliParser()
        events = parser.parse()
        parser.close()
        
        print(f"\n[+] Найдено событий: {len(events)}")
        
        # Выводим первые 3 события
        for i, event in enumerate(events[:3], 1):
            print(f"\n--- Событие #{i} ---")
            print(f"Название: {event.title}")
            print(f"Дата: {event.event_date}")
            print(f"Место: {event.location}")
            if event.description:
                desc = event.description[:100] + "..." if len(event.description) > 100 else event.description
                print(f"Описание: {desc}")
        
        return events
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        return []

def test_ppbali():
    """Тест парсинга PP Bali."""
    print("\n" + "="*60)
    print("Тестирование: PP Bali (ppbali.com)")
    print("="*60)
    
    try:
        parser = PPBaliParser()
        events = parser.parse()
        parser.close()
        
        print(f"\n[+] Найдено событий: {len(events)}")
        
        # Выводим первые 3 события
        for i, event in enumerate(events[:3], 1):
            print(f"\n--- Событие #{i} ---")
            print(f"Название: {event.title}")
            print(f"Дата: {event.event_date}")
            print(f"Место: {event.location}")
            if event.price:
                print(f"Цена: {event.price}")
        
        return events
        
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        return []

def main():
    """Главная функция."""
    print("="*60)
    print("БЫСТРЫЙ ТЕСТ ПАРСИНГА ВЕБ-САЙТОВ")
    print("="*60)
    
    # Тестируем сайты
    all_events = []
    
    events1 = test_venasobali()
    all_events.extend(events1)
    
    events2 = test_ppbali()
    all_events.extend(events2)
    
    print("\n" + "="*60)
    print(f"ИТОГО: собрано {len(all_events)} событий")
    print("="*60)

if __name__ == "__main__":
    main()
