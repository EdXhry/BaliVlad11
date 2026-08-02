"""
API парсеры — получаем данные через публичные REST API (JSON формат).

Eventbrite — крупнейшая платформа мероприятий, имеет публичный API.
Не требует API ключа для базовых запросов (публичные события).
"""
import logging
from datetime import date, datetime
from typing import Optional
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


class EventbriteApiParser(BaseParser):
    """
    Парсер Eventbrite API.
    
    Eventbrite — международная платформа с кучей событий на Бали.
    API возвращает JSON, поэтому данные уже структурированы.
    
    Документация: https://www.eventbrite.com/platform/api
    """

    # Публичный поиск без авторизации (ограничен, но работает)
    BASE_URL = "https://www.eventbriteapi.com/v3/events/search/"
    SOURCE_NAME = "Eventbrite"

    def __init__(self, api_token: Optional[str] = None):
        super().__init__()
        self.api_token = api_token
        if api_token:
            self.client.headers["Authorization"] = f"Bearer {api_token}"

    def parse(self) -> list[RawEvent]:
        logger.info(f"[{self.SOURCE_NAME}] Запрашиваем события через API")
        events = []

        try:
            params = {
                "location.address": "Bali, Indonesia",
                "location.within": "50km",
                "start_date.range_start": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expand": "venue,category",
                "page_size": 50,
            }

            response = self._get(self.BASE_URL, params=params)
            data = response.json()

            raw_events = data.get("events", [])
            logger.info(f"[{self.SOURCE_NAME}] API вернул {len(raw_events)} событий")

            for raw in raw_events:
                event = self._parse_event(raw)
                if event:
                    events.append(event)

        except Exception as e:
            logger.error(f"[{self.SOURCE_NAME}] Ошибка API запроса: {e}", exc_info=True)

        return events

    def _parse_event(self, raw: dict) -> Optional[RawEvent]:
        """Преобразовать JSON объект события в RawEvent."""
        try:
            # Название
            name = raw.get("name", {}).get("text") or raw.get("name", {}).get("html", "")
            if not name or len(name) < 3:
                return None

            # Дата начала (ISO формат: 2026-07-15T19:00:00)
            start = raw.get("start", {})
            date_str = start.get("local") or start.get("utc")
            if not date_str:
                return None

            event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
            if event_dt.date() < date.today():
                return None

            # Место проведения
            venue = raw.get("venue", {})
            location_parts = [
                venue.get("name"),
                venue.get("address", {}).get("localized_address_display"),
            ]
            location = ", ".join(p for p in location_parts if p) or "Bali, Indonesia"

            # Цена
            is_free = raw.get("is_free", False)
            if is_free:
                price = "Free"
            else:
                ticket_availability = raw.get("ticket_availability", {})
                min_price = ticket_availability.get("minimum_ticket_price", {})
                price_val = min_price.get("display")
                price = price_val or None

            # Категория
            category_obj = raw.get("category", {})
            category = self._map_category(category_obj.get("name", ""))

            # URL
            source_url = raw.get("url", "https://www.eventbrite.com")

            # Описание
            description_obj = raw.get("description", {})
            description = description_obj.get("text") if description_obj else None
            if description:
                description = description[:500]  # Обрезаем длинные описания

            return RawEvent(
                title=name[:200],
                event_date=event_dt.date(),
                event_time=event_dt.time(),
                location=location,
                source_url=source_url,
                source_name=self.SOURCE_NAME,
                description=description,
                price=price,
                category=category,
            )

        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка парсинга события: {e}")
            return None

    def _map_category(self, category_name: str) -> Optional[str]:
        """Привести категорию Eventbrite к нашей системе категорий."""
        mapping = {
            "Music": "music",
            "Performing & Visual Arts": "art",
            "Sports & Fitness": "sport",
            "Science & Technology": "education",
            "Food & Drink": "food",
            "Arts": "art",
            "Film, Media & Entertainment": "music",
        }
        return mapping.get(category_name)


class BaliBestGuideApiParser(BaseParser):
    """
    Парсер через неофициальный JSON endpoint сайта bali-best-guide.com.
    
    Некоторые сайты, хоть и не предоставляют официальный API,
    имеют JSON endpoint-ы которые используются их собственным фронтом.
    """

    SOURCE_URL = "https://www.bali-best-guide.com/bali-events.html"
    SOURCE_NAME = "Bali Best Guide"

    def parse(self) -> list[RawEvent]:
        logger.info(f"[{self.SOURCE_NAME}] Начинаем парсинг {self.SOURCE_URL}")
        events = []

        try:
            from bs4 import BeautifulSoup
            response = self._get(self.SOURCE_URL)
            soup = BeautifulSoup(response.text, "lxml")

            # Ищем события в HTML таблицах или списках
            rows = soup.select("table tr, .event-row, .event-entry")

            for row in rows:
                cells = row.find_all(["td", "div", "span"])
                if len(cells) < 2:
                    continue

                texts = [c.get_text(strip=True) for c in cells]

                # Ищем строку похожую на название события
                title = texts[0] if texts[0] and len(texts[0]) >= 3 else None
                if not title:
                    continue

                # Ищем дату среди ячеек
                event_date = None
                for text in texts[1:]:
                    from parsers.html_parser import BaliEventsHtmlParser
                    parsed = BaliEventsHtmlParser._parse_date(None, text)
                    if parsed and parsed >= date.today():
                        event_date = parsed
                        break

                if not event_date:
                    continue

                # Ссылка
                link = row.find("a")
                source_url = link.get("href", self.SOURCE_URL) if link else self.SOURCE_URL
                if source_url.startswith("/"):
                    source_url = "https://www.bali-best-guide.com" + source_url

                events.append(RawEvent(
                    title=title[:200],
                    event_date=event_date,
                    location="Bali, Indonesia",
                    source_url=source_url,
                    source_name=self.SOURCE_NAME,
                ))

            logger.info(f"[{self.SOURCE_NAME}] Спаршено {len(events)} событий")

        except Exception as e:
            logger.error(f"[{self.SOURCE_NAME}] Ошибка: {e}", exc_info=True)

        return events
