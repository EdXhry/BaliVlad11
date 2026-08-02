"""
Тестовый скрипт для проверки парсинга источников.
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
from parsers.base import RawEvent
import json
import yaml

def load_sources():
    """Загрузить источники из файла."""
    with open("sources.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_config():
    """Загрузить конфигурацию."""
    with open("source_configs.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def test_source(source_config, config):
    """Протестировать парсинг одного источника."""
    name = source_config.get("name")
    source_type = source_config.get("type")
    
    print(f"\n{'='*60}")
    print(f"Тестирование: {name} ({source_type})")
    print(f"{'='*60}")
    
    try:
        # Определяем URL
        if source_type == "telegram":
            url = source_config.get("username", "")
        else:
            url = source_config.get("url", "")
        
        # Определяем правила парсинга
        if source_type == "telegram":
            telegram_config = config.get("telegram", {})
            parsing_rules = {
                "content_selector": telegram_config.get("content_selector", ".tgme_widget_message_text"),
                "date_format": "telegram",
                "default_location": "Online / Bali, Indonesia",
            }
        else:
            # Используем правила по умолчанию для вебсайтов
            sources_config = config.get("sources", {})
            
            # Пробуем найти специфичные правила для сайта
            site_name = name.lower()
            url_lower = url.lower()
            
            parsing_rules = {}
            for key, site_config in sources_config.items():
                if isinstance(site_config, dict):
                    site_url = site_config.get("url", "").lower()
                    site_config_name = site_config.get("name", "").lower()
                    if (url_lower == site_url or 
                        site_name in key.lower() or 
                        key.lower() in site_name or
                        site_config_name == site_name):
                        # Нашли специфичные правила
                        site_rules = site_config.get("parsing_rules", {})
                        if site_rules:
                            parsing_rules.update(site_rules)
                        break
            
            # Если не нашли - используем default_website
            if not parsing_rules:
                default_config = sources_config.get("default_website", {})
                parsing_rules = default_config.get("parsing_rules", {})
        
        # Создаем парсер
        parser = UniversalParser(name, url, parsing_rules, source_type)
        
        # Запускаем парсинг
        events = parser.parse()
        
        print(f"\n[+] Найдено событий: {len(events)}")
        
        # Выводим первые 3 события
        for i, event in enumerate(events[:3], 1):
            print(f"\n--- Событие #{i} ---")
            print(f"Название: {event.title}")
            print(f"Дата: {event.event_date}")
            print(f"Место: {event.location}")
            print(f"Источник: {event.source_name}")
            if event.description:
                desc = event.description[:100] + "..." if len(event.description) > 100 else event.description
                print(f"Описание: {desc}")
        
        # Закрываем парсер
        parser.close()
        
        return events
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании {name}: {e}", exc_info=True)
        return []

def main():
    """Главная функция тестирования."""
    print("="*60)
    print("ТЕСТИРОВАНИЕ ПАРСИНГА ИСТОЧНИКОВ")
    print("="*60)
    
    # Загружаем источники
    sources = load_sources()
    config = load_config()
    
    print(f"\nЗагружено {len(sources)} источников:")
    for i, source in enumerate(sources, 1):
        status = "[+]" if source.get("enabled") else "[-]"
        print(f"  {i}. {status} {source.get('name')} ({source.get('type')})")
    
    # Тестируем каждый источник
    all_events = []
    for source in sources:
        if not source.get("enabled"):
            continue
        
        events = test_source(source, config)
        all_events.extend(events)
    
    print(f"\n{'='*60}")
    print(f"ИТОГО: собрано {len(all_events)} событий")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
