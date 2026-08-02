"""
Парсеры для источников по недвижимости на Бали (тестовые).
Пока используем заглушки — позже заменим на реальные источники.
"""
import logging
from datetime import date, time, datetime, timedelta
import random
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


class TestRealEstateParser(BaseParser):
    """
    Тестовый парсер для демонстрации ТЗ фильтрации.
    Генерирует искусственные события по недвижимости на Бали.
    """
    
    SOURCE_NAME = "Тестовые данные"

    def parse(self) -> list[RawEvent]:
        """Генерировать тестовые события для демонстрации ТЗ."""
        logger.info("Генерация тестовых данных по ТЗ недвижимости...")
        
        # Создаём список тестовых событий (40% пройдут фильтры)
        events = [
            # ПРОЙДУТ ФИЛЬТРЫ
            self._create_test_event(
                title="Инвестиционный форум недвижимости Бали",
                description="Ежегодная конференция по инвестициям в недвижимость. Спикер: Иван Петров (RealEstateBali)",
                location="Seminyak, Bali",
                category="investment",
                language="ru",
                is_online=False,
            ),
            self._create_test_event(
                title="Property Management Meetup Canggu",
                description="Встреча управляющих недвижимостью. Обмен опытом по аренде вилл.",
                location="Canggu, Bali", 
                category="management",
                language="en",
                is_online=False,
            ),
            self._create_test_event(
                title="Онлайн-конференция: Девелопмент на Бали",
                description="Ведущий: Мария Смирнова. Только для русскоязычной аудитории.",
                location="Zoom",
                category="development",
                language="ru",
                is_online=True,
            ),
            self._create_test_event(
                title="Страта-титулы в Индонезии",
                description="Семинар по правовым аспектам. Спикер: Алексей Ковалёв",
                location="Ubud, Bali",
                category="property",
                language="ru+en",
                is_online=False,
            ),
            
            # НЕ ПРОЙДУТ ФИЛЬТРЫ (для теста)
            self._create_test_event(
                title="Юридические аспекты ВНЖ",
                description="Вебинар по миграционному праву",  # исключение по ТЗ
                location="Bali",
                category="property",
                language="ru",
                is_online=False,
            ),
            self._create_test_event(
                title="Мастер-класс по дизайну интерьеров",  # не недвижимость
                location="Jakarta",  # не Бали
                language="en",
                is_online=False,
            ),
            self._create_test_event(
                title="Webinar: Bali Real Estate ROI",  # онлайн не на RU
                location="Online",
                language="en",
                is_online=True,
            ),
        ]
        
        logger.info(f"Сгенерировано {len(events)} тестовых событий")
        return events

    def _create_test_event(self, title: str, location: str, language: str, 
                           is_online: bool = False, category: str = "property",
                           description: str = None):
        """Создать тестовое событие."""
        # Генерируем дату в ближайшие 14 дней
        days_offset = random.randint(1, 14)
        event_date = date.today() + timedelta(days=days_offset)
        
        # Время для оффлайн
        event_time = None
        if not is_online:
            event_time = time(hour=random.randint(9, 20), minute=random.choice([0, 30]))
        
        return RawEvent(
            title=title,
            event_date=event_date,
            event_time=event_time,
            location=location,
            description=description,
            source_url="https://test.example.com/event",
            price=random.choice(["Free", "150k IDR", "500k IDR", None]),
            category=category,
            source_name=self.SOURCE_NAME,
        )


class TelegramChannelParser(BaseParser):
    """
    Заглушка для парсера Telegram каналов.
    Позже заменим на реальный парсинг через Telethon/pyrogram.
    """
    
    def __init__(self, channel_username: str):
        super().__init__()
        self.channel_username = channel_username
        self.SOURCE_NAME = f"Telegram: {channel_username}"

    def parse(self) -> list[RawEvent]:
        """Заглушка — возвращает пустой список."""
        logger.info(f"Парсинг Telegram канала {self.channel_username} (заглушка)")
        # TODO: Реализовать через Telethon
        return []


class RealEstateWebsiteParser(BaseParser):
    """
    Заглушка для парсера сайтов по недвижимости.
    """
    
    def __init__(self, url: str, name: str):
        super().__init__()
        self.url = url
        self.SOURCE_NAME = name

    def parse(self) -> list[RawEvent]:
        """Заглушка — возвращает пустой список."""
        logger.info(f"Парсинг сайта {self.SOURCE_NAME} (заглушка)")
        # TODO: Реализовать реальный парсинг
        return []
