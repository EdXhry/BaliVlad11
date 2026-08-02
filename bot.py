"""
Telegram бот для публикации мероприятий Бали.

Прокси нужен для работы в России — Telegram заблокирован.
Прокси формат: http://user:password@ip:port
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError, NetworkError, RetryAfter
from telegram.request import HTTPXRequest
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Настройки из .env ────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@testbotrurururu")
PROXY_URL = os.getenv("PROXY_URL")  # http://user:password@ip:port

# ─── Константы retry ──────────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 300   # 5 минут между попытками
TELEGRAM_DOWN_DELAY = 600   # 10 минут если Telegram недоступен


def create_bot() -> Bot:
    """
    Создать Bot с поддержкой прокси.
    
    Как работает прокси:
    - HTTPX (HTTP клиент внутри python-telegram-bot) поддерживает HTTP/SOCKS прокси
    - Все запросы к api.telegram.org идут через прокси сервер
    - Прокси сервер находится за рубежом и не подпадает под блокировку
    """
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env файле!")

    if PROXY_URL:
        logger.info(f"Используем прокси: {PROXY_URL.split('@')[1] if '@' in PROXY_URL else PROXY_URL}")
        # HTTPXRequest позволяет задать прокси для всех запросов бота
        request = HTTPXRequest(proxy=PROXY_URL)
        bot = Bot(token=BOT_TOKEN, request=request)
    else:
        logger.warning("Прокси не задан. Может не работать в России.")
        bot = Bot(token=BOT_TOKEN)

    return bot


async def test_connection() -> bool:
    """Проверить подключение к Telegram API."""
    bot = create_bot()
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот подключен: @{me.username} ({me.first_name})")
        return True
    except NetworkError as e:
        logger.error(f"❌ Сетевая ошибка: {e}")
        logger.error("Проверьте прокси и интернет соединение")
        return False
    except TelegramError as e:
        logger.error(f"❌ Ошибка Telegram: {e}")
        return False
    finally:
        await bot.shutdown()


async def publish_digest(text: str) -> Optional[str]:
    """
    Опубликовать подборку в Telegram канал.
    
    Возвращает ID сообщения при успехе или None при ошибке.
    Автоматически повторяет попытку при временных ошибках.
    """
    bot = create_bot()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Публикация в {CHANNEL_ID} (попытка {attempt}/{MAX_RETRIES})")

            message = await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            msg_id = str(message.message_id)
            logger.info(f"✅ Опубликовано! ID сообщения: {msg_id}")
            return msg_id

        except RetryAfter as e:
            # Telegram просит подождать (rate limit)
            wait = e.retry_after + 5
            logger.warning(f"Telegram rate limit. Ждём {wait} секунд...")
            await asyncio.sleep(wait)

        except NetworkError as e:
            logger.warning(f"Попытка {attempt}: Сетевая ошибка: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Повтор через {TELEGRAM_DOWN_DELAY} сек...")
                await asyncio.sleep(TELEGRAM_DOWN_DELAY)

        except TelegramError as e:
            logger.error(f"Попытка {attempt}: Ошибка Telegram: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

        except Exception as e:
            logger.error(f"Попытка {attempt}: Неожиданная ошибка: {e}", exc_info=True)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

        finally:
            if attempt == MAX_RETRIES:
                await bot.shutdown()

    logger.error(f"❌ Все {MAX_RETRIES} попытки публикации неудачны")
    return None


async def send_test_message() -> bool:
    """
    Отправить тестовое сообщение в канал.
    Используется для проверки что бот работает корректно.
    """
    test_text = (
        "📅 *Тестовая подборка*\n\n"
        "*26 июня \\(пятница\\)*\n\n"
        "🎵 [*Beach Sunset Party*](https://example.com)\n"
        "   _19:00_ • 📍 Seminyak Beach • 💰 Free\n\n"
        "🎨 [*Art Exhibition Opening*](https://example.com)\n"
        "   _18:00_ • 📍 Ubud Gallery • 💰 50k IDR\n\n"
        "_Это тестовое сообщение от Bali Events Bot_ 🌴"
    )

    bot = create_bot()
    try:
        message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=test_text,
            parse_mode="MarkdownV2",
        )
        logger.info(f"✅ Тестовое сообщение отправлено! ID: {message.message_id}")
        await bot.shutdown()
        return True
    except TelegramError as e:
        logger.error(f"❌ Ошибка отправки тестового сообщения: {e}")
        await bot.shutdown()
        return False


def _strip_markdown(text: str) -> str:
    """Убрать Markdown форматирование — fallback при ошибке парсинга."""
    import re
    # Убираем ссылки [текст](url) -> текст
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Убираем *, _, ~, `
    text = re.sub(r"[*_~`\\]", "", text)
    return text


# ─── Запуск напрямую для теста ────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    async def main():
        print("=" * 50)
        print("Тест Telegram бота")
        print("=" * 50)

        # 1. Проверяем подключение
        print("\n1. Проверяем подключение к Telegram API...")
        connected = await test_connection()
        if not connected:
            print("\n❌ Не удалось подключиться. Проверьте токен и прокси.")
            return

        # 2. Отправляем тестовое сообщение
        print(f"\n2. Отправляем тестовое сообщение в {CHANNEL_ID}...")
        success = await send_test_message()
        if success:
            print(f"\n✅ Успех! Проверьте канал {CHANNEL_ID}")
        else:
            print(f"\n❌ Не удалось отправить сообщение")
            print("   Убедитесь что бот добавлен администратором в канал!")

    asyncio.run(main())
