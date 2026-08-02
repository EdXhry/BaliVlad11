"""
Простой рабочий скрипт для парсинга и публикации.
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
        
        # Ищем заголовки, содержащие ключевые слова недвижимости
        property_keywords = [
            'property', 'real estate', 'villa', 'apartment', 'land', 'sale',
            'rent', 'investment', 'development', 'construction', 'project'
        ]
        
        # Поиск всех заголовков и ссылок
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            for header in soup.find_all(tag):
                text = header.get_text(strip=True).lower()
                
                # Проверяем содержит ли заголовок ключевые слова недвижимости
                for keyword in property_keywords:
                    if keyword in text:
                        # Пытаемся найти родительский контейнер или ссылку
                        link = None
                        parent = header.find_parent('a')
                        if parent and parent.get('href'):
                            href = parent.get('href')
                            if href.startswith('/'):
                                link = f"https://ppbali.com{href}"
                            elif href.startswith('http'):
                                link = href
                        
                        # Ищем описание
                        description = ""
                        next_sibling = header.find_next_sibling('p')
                        if next_sibling:
                            description = next_sibling.get_text(strip=True)[:150]
                        
                        events.append({
                            'title': header.get_text(strip=True),
                            'link': link or url,
                            'description': description,
                            'date': date.today()  # Берем сегодняшнюю дату
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
    
    lines = ["📅 *Дайджест недвижимости на Бали*\n"]
    
    for i, event in enumerate(events[:10]):  # Ограничим 10 событиями
        title = escape_markdown(event['title'])
        link = event['link']
        description = escape_markdown(event['description']) if event['description'] else ""
        event_date = event['date'].strftime("%d.%m.%Y")
        
        # Форматируем событие
        lines.append(f"\n*{i+1}. {title}*")
        lines.append(f"📅 *{event_date}*")
        if description:
            lines.append(f"📝 {description}")
        lines.append(f"🔗 [Подробнее]({link})")
    
    lines.append(f"\n*Всего найдено {len(events)} событий*")
    
    return "\n".join(lines)


def escape_markdown(text):
    """Экранировать спецсимволы для MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
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
                'title': 'Тестовое событие: Инвестиции в Бали недвижимость',
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