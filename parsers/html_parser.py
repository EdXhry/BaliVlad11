"""
HTML парсеры для сайтов с мероприятиями на Бали.

Каждый класс = один сайт-источник.
BeautifulSoup читает HTML и извлекает данные по CSS селекторам.
"""
import logging
import re
from datetime import date, datetime
from typing import Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


def _safe_text(element) -> Optional[str]:
    """Безопасно извлечь текст из BS4 элемента."""
    if element is None:
        return None
    return element.get_text(strip=True) or None


def _safe_attr(element, attr: str) -> Optional[str]:
    """Безопасно извлечь атрибут из BS4 элемента."""
    if element is None:
        return None
    return element.get(attr)


class BaliEventsHtmlParser(BaseParser):
    """
    Парсер сайта balievents.com
    
    Как работает:
    1. Делаем GET запрос на страницу со списком событий
    2. BS4 парсит HTML
    3. Находим все карточки событий по CSS классам
    4. Из каждой карточки извлекаем нужные поля
    """

    SOURCE_URL = "https://www.balievents.com/events"
    SOURCE_NAME = "BaliEvents.com"

    def parse(self) -> list[RawEvent]:
        logger.info(f"[{self.SOURCE_NAME}] Начинаем парсинг {self.SOURCE_URL}")
        events = []

        try:
            response = self._get(self.SOURCE_URL)
            soup = BeautifulSoup(response.text, "lxml")

            # Ищем карточки событий (CSS классы могут отличаться — нужно проверить на реальном сайте)
            event_cards = soup.select(".event-item, .event-card, article.event, .events-list .item")

            if not event_cards:
                # Если специфичных карточек нет — ищем общие контейнеры
                event_cards = soup.select("[class*='event']")
                logger.warning(f"[{self.SOURCE_NAME}] Не найдены стандартные карточки, найдено {len(event_cards)} по общему селектору")

            for card in event_cards:
                event = self._parse_card(card)
                if event:
                    events.append(event)

            logger.info(f"[{self.SOURCE_NAME}] Спаршено {len(events)} событий")

        except Exception as e:
            logger.error(f"[{self.SOURCE_NAME}] Ошибка парсинга: {e}", exc_info=True)

        return events

    def _parse_card(self, card) -> Optional[RawEvent]:
        """Извлечь данные из одной карточки события."""
        try:
            # Пробуем разные селекторы для названия
            title_el = (
                card.select_one("h2, h3, h4, .event-title, .title, [class*='title']")
            )
            title = _safe_text(title_el)
            if not title or len(title) < 3:
                return None  # Без названия событие бесполезно

            # Дата
            date_el = card.select_one(".event-date, .date, time, [class*='date'], [datetime]")
            event_date = self._parse_date(
                _safe_text(date_el) or _safe_attr(date_el, "datetime")
            )
            if not event_date or event_date < date.today():
                return None  # Пропускаем прошедшие события

            # Место
            location_el = card.select_one(".venue, .location, .place, [class*='venue'], [class*='location']")
            location = _safe_text(location_el) or "Bali, Indonesia"

            # Ссылка на источник
            link_el = card.select_one("a[href]")
            source_url = _safe_attr(link_el, "href") or self.SOURCE_URL
            if source_url.startswith("/"):
                source_url = "https://www.balievents.com" + source_url

            # Цена (опционально)
            price_el = card.select_one(".price, .ticket-price, [class*='price']")
            price = _safe_text(price_el)

            # Описание (опционально)
            desc_el = card.select_one(".description, .excerpt, p, [class*='desc']")
            description = _safe_text(desc_el)

            return RawEvent(
                title=title[:200],  # Ограничиваем 200 символами
                event_date=event_date,
                location=location,
                source_url=source_url,
                source_name=self.SOURCE_NAME,
                description=description,
                price=price,
                category=self._guess_category(title, description),
            )

        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка при парсинге карточки: {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """
        Пробуем распарсить дату из разных форматов.
        Сайты часто используют разные форматы дат.
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Форматы которые чаще всего встречаются
        formats = [
            "%Y-%m-%d",          # 2026-07-15
            "%d.%m.%Y",          # 15.07.2026
            "%d/%m/%Y",          # 15/07/2026
            "%B %d, %Y",         # July 15, 2026
            "%d %B %Y",          # 15 July 2026
            "%b %d, %Y",         # Jul 15, 2026
            "%Y-%m-%dT%H:%M",    # 2026-07-15T19:00 (ISO формат)
            "%Y-%m-%dT%H:%M:%S", # 2026-07-15T19:00:00
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str[:len(fmt)], fmt).date()
            except ValueError:
                continue

        # Ищем паттерн "цифры-цифры-цифры" в строке
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass

        logger.debug(f"Не удалось распарсить дату: {date_str!r}")
        return None

    def _guess_category(self, title: str, description: Optional[str]) -> Optional[str]:
        """Определить категорию по ключевым словам в названии/описании."""
        text = (title + " " + (description or "")).lower()

        if any(w in text for w in ["music", "concert", "dj", "festival", "band", "live", "музык", "концерт"]):
            return "music"
        if any(w in text for w in ["art", "exhibition", "gallery", "искусств", "выставк"]):
            return "art"
        if any(w in text for w in ["yoga", "sport", "surf", "fitness", "run", "yoga", "спорт"]):
            return "sport"
        if any(w in text for w in ["workshop", "seminar", "class", "learn", "воркшоп", "обучение"]):
            return "education"
        if any(w in text for w in ["food", "market", "bazaar", "еда", "маркет", "рынок"]):
            return "food"

        return None


class TimeOutBaliParser(BaseParser):
    """
    Парсер сайта timeoutbali.com — популярный агрегатор событий на Бали.
    
    Аналогичная логика — BS4 + CSS селекторы.
    """

    SOURCE_URL = "https://www.timeoutbali.com/things-to-do/events/"
    SOURCE_NAME = "TimeOut Bali"

    def parse(self) -> list[RawEvent]:
        logger.info(f"[{self.SOURCE_NAME}] Начинаем парсинг {self.SOURCE_URL}")
        events = []

        try:
            response = self._get(self.SOURCE_URL)
            soup = BeautifulSoup(response.text, "lxml")

            # TimeOut использует карточки с классом tile
            event_cards = soup.select("._card, li[data-tracking-label], article")

            for card in event_cards:
                event = self._parse_card(card)
                if event:
                    events.append(event)

            logger.info(f"[{self.SOURCE_NAME}] Спаршено {len(events)} событий")

        except Exception as e:
            logger.error(f"[{self.SOURCE_NAME}] Ошибка парсинга: {e}", exc_info=True)

        return events

    def _parse_card(self, card) -> Optional[RawEvent]:
        try:
            title_el = card.select_one("h3, h2, ._headline, [class*='headline'], [class*='title']")
            title = _safe_text(title_el)
            if not title or len(title) < 3:
                return None

            # TimeOut часто хранит дату в атрибуте data-*
            date_el = card.select_one("time, [class*='date'], [data-date]")
            date_str = (
                _safe_attr(date_el, "datetime")
                or _safe_attr(date_el, "data-date")
                or _safe_text(date_el)
            )
            event_date = BaliEventsHtmlParser._parse_date(self, date_str)
            if not event_date or event_date < date.today():
                return None

            location_el = card.select_one("[class*='venue'], [class*='location'], address")
            location = _safe_text(location_el) or "Bali"

            link_el = card.select_one("a[href]")
            source_url = _safe_attr(link_el, "href") or self.SOURCE_URL
            if source_url.startswith("/"):
                source_url = "https://www.timeoutbali.com" + source_url

            price_el = card.select_one("[class*='price'], [class*='cost']")
            price = _safe_text(price_el)

            return RawEvent(
                title=title[:200],
                event_date=event_date,
                location=location,
                source_url=source_url,
                source_name=self.SOURCE_NAME,
                price=price,
            )
        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка парсинга карточки: {e}")
            return None
