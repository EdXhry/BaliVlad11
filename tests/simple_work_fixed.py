"""
Простой рабочий скрипт для парсинга и публикации с исправленным экранированием.
"""
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import date
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Импортируем бота
from bot import publish_digest, test_connection


def parse_ppbali():
    """Парсинг сайта ppbali.com"""
    print("🔍 Парсинг ppbali.com...")
    
    try:
        url = "https://ppbali.com"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        events = []
        
        # Ищем ключевые слова недвижимости
        property_keywords = [
            'property', 'real estate', 'villa', 'apartment', 'land', 'sale',
            'rent', 'investment', 'development', 'construction', 'project'
        ]
        
        # Ищем все ссылки на странице
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            href = link.get('href')
            
            if not text or len(text) < 10:
                continue
                
            text_lower = text.lower()
            
            # Проверяем содержит ли текст ключевые слова недвижимости
            for keyword in property_keywords:
                if keyword in text_lower:
                    # Получаем полный URL
                    full_url = href
                    if href.startswith('/'):
                        full_url = f"https://ppbali.com{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    events.append({
                        'title': text[:100],  # Ограничиваем длину
                        'link': full_url,
                        'description': '',
                        'date': date.today()
                    })
                    break
        
        print(f"Найдено {len(events)} событий на ppbali.com")
        return events
        
    except Exception as e:
        print(f"Ошибка парсинга ppbali.com: {e}")
        return []


def create_digest_from_events(events):
    """Создать подборку из событий."""
    print("📝 Создание подборки...")
    
    if not events:
        return None
    
    lines = ["*Дайджест недвижимости на Бали*\n"]
    
    for i, event in enumerate(events[:5]):  # Ограничим 5 событиями
        title = escape_markdown_v2(event['title'])
        link = event['link']
        description = escape_markdown_v2(event['description']) if event['description'] else ""
        event_date = escape_markdown_v2(event['date'].strftime("%d.%m.%Y"))
        
        # Форматируем событие
        lines.append(f"\n*{i+1}\\. {title}*")
        lines.append(f"📅 *{event_date}*")
        if description:
            lines.append(f"📝 {description}")
        lines.append(f"🔗 [Подробнее]({link})")
    
    lines.append(f"\n*Всего найдено {len(events)} событий*")
    
    return "\n".join(lines)


def escape_markdown_v2(text):
    """Экранировать спецсимволы для MarkdownV2."""
    # В MarkdownV2 нужно экранировать: _ * [ ] ( ) ~ ` > # + - = | { } . !
    special_chars = r"_*[]()~`>#+-=|{}.!"
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


async def main():
    """Главная функция."""
    print("=" * 60)
    print("🏠 Бот недвижимости Бали - рабочий тест")
    print("=" * 60)
    
    # 1. Проверяем подключение к Telegram
    print("\n🤖 Проверка Telegram...")
    connected = await test_connection()
    if not connected:
        print("❌ Telegram не доступен")
        return
    
    print("✅ Telegram доступен")
    
    # 2. Парсим сайты
    print("\n🔍 Парсинг источников...")
    ppbali_events = parse_ppbali()
    
    all_events = ppbali_events
    
    if not all_events:
        print("⚠️  Не найдено событий, используем тестовые данные")
        all_events = [
            {
                'title': 'Инвестиции в Бали недвижимость',
                'link': 'https://ppbali.com',
                'description': 'Новые возможности для инвестиций в недвижимость Бали 2026',
                'date': date.today()
            }
        ]
    
    # 3. Создаем подборку
    digest = create_digest_from_events(all_events)
    
    if not digest:
        print("❌ Не удалось создать подборку")
        return
    
    print(f"\n📄 Подборка ({len(digest)} символов):")
    print("-" * 50)
    print(digest[:300] + "..." if len(digest) > 300 else digest)
    print("-" * 50)
    
    # 4. Публикуем
    print(f"\n📤 Публикация в канал @testbotrurururu...")
    message_id = await publish_digest(digest)
    
    if message_id:
        print(f"✅ Опубликовано! ID: {message_id}")
        print(f"   Проверьте канал @testbotrurururu")
    else:
        print("❌ Не удалось опубликовать")
    
    print("\n" + "=" * 60)
    print("✅ Тест завершен")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())