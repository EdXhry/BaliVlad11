"""
Самый простой тест бота
"""
import asyncio
from bot import publish_digest


async def main():
    print("🤖 Тест Telegram бота")
    
    # Супер простое сообщение без форматирования
    simple_message = """Бали недвижимость
    
Новые проекты:
- Кута: Вилла 200к USD
- Семиньяк: Апартаменты 150к USD  
- Убуд: Земельный участок 100к USD

Сайт: ppbali.com
Канал: @bali_invest"""
    
    print("Отправляем простое сообщение...")
    result = await publish_digest(simple_message)
    
    if result:
        print(f"✅ Сообщение отправлено! ID: {result}")
    else:
        print("❌ Не удалось отправить")


if __name__ == "__main__":
    asyncio.run(main())