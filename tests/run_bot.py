"""
Проверка и запуск бота с реальными источниками.
"""
import logging
import asyncio
import requests
from datetime import datetime
from sqlalchemy.orm import Session

from database import SessionLocal, init_db, check_connection
from bot import publish_digest, test_connection, send_test_message
from digest import compile_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def test_web_sources():
    """Проверить доступность веб-сайтов."""
    print("🌐 Проверка доступности веб-сайтов...")
    
    sources = [
        ("Venaso Bali", "https://venasobali.com.au"),
        ("PP Bali", "https://ppbali.com"),
        ("Mirah Developments", "https://mirahdevelopments.com/residential-real-estate/")
    ]
    
    for name, url in sources:
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                print(f"✅ {name}: {url} - доступен ({response.status_code})")
                # Проверим что это HTML страница
                if 'html' in response.headers.get('content-type', '').lower():
                    print(f"   ✓ HTML страница загружена ({len(response.text)} символов)")
                else:
                    print(f"   ⚠️  Не HTML контент: {response.headers.get('content-type')}")
            else:
                print(f"❌ {name}: {url} - ошибка {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: {url} - ошибка: {e}")


async def test_telegram_bot():
    """Проверить работу Telegram бота."""
    print("\n🤖 Проверка Telegram бота...")
    
    # Проверяем подключение к Telegram
    connected = await test_connection()
    if not connected:
        print("❌ Не удалось подключиться к Telegram API")
        print("   Проверьте токен бота и прокси")
        return False
    
    print("✅ Подключение к Telegram успешно")
    
    # Отправляем тестовое сообщение
    success = await send_test_message()
    if success:
        print("✅ Тестовое сообщение отправлено")
        print("   Проверьте канал @testbotrurururu")
    else:
        print("⚠️  Не удалось отправить тестовое сообщение")
        print("   Бот может не иметь прав администратора в канале")
    
    return True


def test_database():
    """Проверить подключение к базе данных."""
    print("\n🗄️  Проверка базы данных...")
    
    if check_connection():
        print("✅ Подключение к PostgreSQL успешно")
        
        # Инициализируем базу данных
        init_db()
        print("✅ База данных инициализирована")
        return True
    else:
        print("❌ Ошибка подключения к PostgreSQL")
        print("   Убедитесь что PostgreSQL запущен и база bali_events создана")
        print("   Команда для создания базы: createdb bali_events")
        return False


def create_sample_digest():
    """Создать примерную подборку для теста."""
    print("\n📝 Создание примерной подборки...")
    
    # Пример подборки с реальными данными
    sample_digest = """📅 *Дайджест событий по недвижимости на Бали*

*📆 26 июня (пятница) • WITA*

📅 26 июня 2026, _14:00 WITA_
📍 *Санур, Бали*
🏷 ОФФЛАЙН | Тип: выставка
🧵 *Выставка недвижимости на Бали: новые проекты 2026*
🗣 Бали Реал Эстейт Групп
Язык: 🇷🇺🇬🇧 RU+EN
🔗 [Подробнее](https://venasobali.com.au)

📅 27 июня 2026, _11:00 WITA_
📍 *Семиньяк, Бали*
🏷 ОФФЛАЙН | Тип: встреча
🧵 *Инвестиции в коммерческую недвижимость Бали 2026*
🗣 Terra Auri Investment Group
Язык: 🇷🇺 RU
🔗 [Подробнее](https://t.me/terraauri)

📅 28 июня 2026, _15:00 WITA_
📍 *Кута, Бали*
🏷 ОФФЛАЙН | Тип: форум
🧵 *Форум девелоперов Бали: новые проекты развития*
🗣 Bali Invest Community
Язык: 🇬🇧 EN
🔗 [Подробнее](https://t.me/bali_invest)

📅 29 июня 2026, _10:00 WITA_
📍 *Убуд, Бали*
🏷 ОФФЛАЙН | Тип: семинар
🧵 *Семинар: Как инвестировать в виллы на Бали*
🗣 PP Bali Real Estate
Язык: 🇷🇺🇬🇧 RU+EN
🔗 [Подробнее](https://ppbali.com)

*Найдено 4 события за 24 ч.*"""
    
    print("Примерная подборка создана:")
    print("-" * 60)
    print(sample_digest[:500] + "..." if len(sample_digest) > 500 else sample_digest)
    print("-" * 60)
    
    return sample_digest


async def run_manual_test():
    """Запустить ручной тест всего функционала."""
    print("=" * 60)
    print("🚀 Тестирование бота Бали недвижимость")
    print("=" * 60)
    
    # 1. Проверяем доступность источников
    test_web_sources()
    
    # 2. Проверяем базу данных
    if not test_database():
        return
    
    # 3. Проверяем Telegram бота
    if not await test_telegram_bot():
        return
    
    # 4. Создаем примерную подборку
    sample_digest = create_sample_digest()
    
    # 5. Публикуем примерную подборку
    print("\n📤 Публикация примерной подборки...")
    message_id = await publish_digest(sample_digest)
    
    if message_id:
        print(f"✅ Подборка опубликована! ID сообщения: {message_id}")
        print("   Проверьте канал @testbotrurururu")
    else:
        print("❌ Не удалось опубликовать подборку")
        print("   Проверьте логи для деталей ошибки")
    
    print("\n" + "=" * 60)
    print("📋 Информация о системе:")
    print(f"   Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Источники: 2 Telegram канала, 3 веб-сайта")
    print(f"   Канал публикации: @testbotrurururu")
    print("=" * 60)
    
    print("\n💡 Дальнейшие действия:")
    print("   1. Проверьте канал @testbotrurururu - должна быть тестовая публикация")
    print("   2. Если всё работает - можно настроить автоматический сбор данных")
    print("   3. Для добавления новых источников используйте панель управления")
    print("      (запустите панель: python panel.py)")


if __name__ == "__main__":
    asyncio.run(run_manual_test())