"""
Простой тест универсального парсера.
"""
import logging
import sys
from collector import load_config, create_parser_for_source

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def main():
    print("🚀 Тест универсального парсера")
    print("=" * 60)
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Тестируем разные типы источников
    test_cases = [
        {
            "name": "Telegram: BaliInvest",
            "type": "telegram",
            "username": "@bali_invest"
        },
        {
            "name": "Telegram: TerraAuri",
            "type": "telegram",
            "username": "@terraauri"
        },
        {
            "name": "Venaso Bali Real Estate",
            "type": "website",
            "url": "https://venasobali.com.au"
        },
        {
            "name": "PP Bali Real Estate",
            "type": "website",
            "url": "https://ppbali.com"
        },
        {
            "name": "Тестовые данные",
            "type": "test"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📡 Тестируем: {test_case['name']} ({test_case['type']})")
        print("-" * 40)
        
        try:
            parser = create_parser_for_source(test_case, config)
            if not parser:
                print("❌ Не удалось создать парсер")
                continue
                
            print(f"✓ Парсер создан успешно")
            
            # Запускаем парсинг
            events = parser.parse()
            print(f"✓ Найдено {len(events)} событий")
            
            # Показываем первые 2 события
            if events:
                for i, event in enumerate(events[:2]):
                    print(f"  {i+1}. {event.title[:60]}...")
                    print(f"     📅 {event.event_date} | 📍 {event.location}")
                    if event.description:
                        print(f"     📝 {event.description[:80]}...")
            
            # Закрываем парсер
            if hasattr(parser, 'close'):
                parser.close()
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
    
    # Теперь покажем как легко добавить новый источник
    print("\n💡 Пример добавления нового источника:")
    print("""
from collector import add_source

# Добавить Telegram канал
add_source("telegram", "Новый канал Бали", "@bali_channel")

# Добавить вебсайт
add_source("website", "Новый сайт недвижимости", "https://example.com")

# После этого источник автоматически появится в sources.json
# и будет использоваться при следующем запуске сбора данных
""")

if __name__ == "__main__":
    main()