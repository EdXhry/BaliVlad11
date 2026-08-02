"""
Скрипт первичной авторизации Telegram сессии.

Запусти ОДИН РАЗ:
    venv\Scripts\python.exe init_telegram_session.py

После успешного входа создаётся файл telegram_session.session —
он хранит авторизацию, больше входить не нужно.
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE    = os.getenv("TELEGRAM_PHONE", "")
SESSION  = "telegram_session"


async def main():
    if not API_ID or not API_HASH:
        print("❌ Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH не заданы в .env")
        print("   Получи их на https://my.telegram.org")
        return

    if not PHONE:
        print("❌ Ошибка: TELEGRAM_PHONE не задан в .env")
        print("   Пример: TELEGRAM_PHONE=+79991234567")
        return

    print("=" * 50)
    print("Авторизация Telegram сессии")
    print("=" * 50)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Уже авторизован как: {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    print(f"\nОтправляю код на {PHONE}...")
    await client.send_code_request(PHONE)

    code = input("Введи код из Telegram: ").strip()

    try:
        await client.sign_in(PHONE, code)
    except SessionPasswordNeededError:
        # Двухфакторная аутентификация
        password = input("Введи пароль двухфакторной аутентификации: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\n✅ Успешно авторизован как: {me.first_name} (@{me.username})")
    print(f"   Файл сессии: {SESSION}.session")
    print("\nТеперь можно запускать бота — авторизация больше не нужна.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
