"""
Парсер сайта https://ppbali.com - недвижимость на Бали.
"""
import logging
import re
from datetime import date, datetime
from typing import Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


class PPBaliParser(BaseParser):
    """
    Парсер сайта https://ppbali.com
    Сайт о недвижимости на Бали.
    """
    
    SOURCE_URL = "https://ppbali.com"
    SOURCE_NAME = "PP Bali Real Estate"

    def parse(self) -> list[RawEvent]:
        """
        Парсим мероприятия с сайта ppbali.com
        """
        logger.info(f"[{self.SOURCE_NAME}] Начинаем парсинг {self.SOURCE_URL}")
        events = []

        try:
            response = self._get(self.SOURCE_URL)
            soup = BeautifulSoup(response.text, "lxml")

            # Ищем все посты/события на сайте
            # Будем искать элементы, содержащие информацию о событиях
            event_elements = soup.select(
                "article, .post, .entry, .event-item, .property-item, "
                "div[class*='property'], div[class*='post'], "
                "div[class*='listing'], div[class*='card'], "
                "a[href*='/property'], a[href*='/listing'], "
                "a[href*='/real-estate'], a[href*='/property-for-sale']"
            )

            logger.info(f"[{self.SOURCE_NAME}] Найдено {len(event_elements)} потенциальных событий")

            for element in event_elements:
                event = self._parse_element(element)
                if event:
                    events.append(event)

            logger.info(f"[{self.SOURCE_NAME}] Спаршено {len(events)} событий")
            return events

        except Exception as e:
            logger.error(f"[{self.SOURCE_NAME}] Ошибка парсинга: {e}", exc_info=True)
            return []

    def _parse_element(self, element) -> Optional[RawEvent]:
        """
        Извлечь данные о событии из HTML элемента.
        """
        try:
            # Извлекаем заголовок
            title_el = element.select_one(
                "h1, h2, h3, h4, .title, .post-title, .entry-title, "
                "[class*='title'], a[href], .property-title, .listing-title"
            )
            
            if title_el is None:
                return None
                
            title = title_el.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # Пытаемся найти ссылку
            link_el = element.select_one("a[href]")
            source_url = None
            if link_el and link_el.get("href"):
                href = link_el.get("href")
                if href.startswith("/"):
                    source_url = f"{self.SOURCE_URL}{href}"
                elif href.startswith("http"):
                    source_url = href
                else:
                    source_url = f"{self.SOURCE_URL}/{href}"
            else:
                source_url = self.SOURCE_URL

            # Пытаемся найти дату в тексте
            date_text = self._extract_date_from_text(element.get_text())
            
            # Если дату не нашли, используем сегодня + несколько дней
            event_date = date_text if date_text else date.today()

            # Пытаемся найти описание
            desc_el = element.select_one(
                ".excerpt, .summary, .entry-content, .property-description, "
                ".listing-description, p, [class*='desc'], [class*='content']"
            )
            description = desc_el.get_text(strip=True)[:500] if desc_el else None

            # Пытаемся найти цену
            price_el = element.select_one(".price, .amount, .cost, [class*='price']")
            price = price_el.get_text(strip=True)[:100] if price_el else None

            # Определяем место
            location = self._detect_location(element.get_text())

            # Определяем категорию (всегда недвижимость для этого сайта)
            category = "property"

            return RawEvent(
                title=title[:200],
                event_date=event_date,
                location=location,
                source_url=source_url,
                source_name=self.SOURCE_NAME,
                description=description,
                price=price,
                category=category,
            )

        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка при парсинге элемента: {e}")
            return None

    def _extract_date_from_text(self, text: str) -> Optional[date]:
        """
        Извлечь дату из текста.
        """
        # Ищем паттерны дат
        patterns = [
            r'(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})',  # DD-MM-YYYY
            r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # 15 July 2026
            r'(\w+)\s+(\d{1,2})\s+(\d{4})',  # July 15 2026
            r'(\d{1,2})\s+(\w+)\.\s+(\d{4})',  # 15 July. 2026
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 3:
                        # Пробуем распарсить в зависимости от паттерна
                        if pattern == patterns[0]:  # DD-MM-YYYY
                            day, month, year = match.groups()
                            return date(int(year), int(month), int(day))
                        elif pattern == patterns[1]:  # YYYY-MM-DD
                            year, month, day = match.groups()
                            return date(int(year), int(month), int(day))
                        elif pattern in (patterns[2], patterns[3], patterns[4]):  # Month DD YYYY
                            # Обработка месяца по имени
                            month_names = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            
                            groups = list(match.groups())
                            # Определяем где месяц (по имени)
                            month = None
                            for i, g in enumerate(groups):
                                if g.lower() in month_names:
                                    month = month_names[g.lower()]
                                    del groups[i]
                                    break
                            
                            if month and len(groups) == 2:
                                # Сортируем по величине: больший = день, меньший = год
                                nums = [int(g) for g in groups]
                                day = min(nums)
                                year = max(nums)
                                if year < 100:  # Если год 2-значный
                                    year += 2000
                                return date(year, month, day)
                except (ValueError, TypeError):
                    continue
        return None

    def _detect_location(self, text: str) -> str:
        """
        Определить место проведения из текста.
        """
        text_lower = text.lower()
        
        # Районы Бали по ТЗ
        bali_districts = [
            "bali", "denpasar", "canggu", "ubud", "seminyak", "sanur",
            "kuta", "jimbaran", "uluwatu", "nusa dua", "bukit",
            "nusa dua", "tanah lot", "lovina", "amed", "nusa lembongan",
            "nusa penida", "tegalalang", "tegallalang", "bedugul"
        ]
        
        for district in bali_districts:
            if district in text_lower:
                return district.capitalize() + ", Bali"
        
        # По умолчанию
        return "Bali, Indonesia"