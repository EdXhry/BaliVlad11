"""
Парсер сайта https://mirahdevelopments.com/residential-real-estate/
Девелопер недвижимости на Бали.
"""
import logging
import re
from datetime import date, datetime
from typing import Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


class MirahDevelopmentsParser(BaseParser):
    """
    Парсер сайта https://mirahdevelopments.com/residential-real-estate/
    Девелоперская компания на Бали.
    """
    
    SOURCE_URL = "https://mirahdevelopments.com/residential-real-estate/"
    SOURCE_NAME = "Mirah Developments (Bali Residential)"

    def parse(self) -> list[RawEvent]:
        """
        Парсим мероприятия и новости с сайта Mirah Developments.
        """
        logger.info(f"[{self.SOURCE_NAME}] Начинаем парсинг {self.SOURCE_URL}")
        events = []

        try:
            response = self._get(self.SOURCE_URL)
            soup = BeautifulSoup(response.text, "lxml")

            # Ищем новости, события, анонсы
            # На сайте девелопера может быть информация о презентациях, выставках и т.д.
            event_elements = soup.select(
                ".post, .article, .news-item, .project-item, "
                ".event, .announcement, [class*='post'], [class*='news'], "
                "[class*='event'], [class*='project'], a[href*='/news'], "
                "a[href*='/event'], a[href*='/project']"
            )

            logger.info(f"[{self.SOURCE_NAME}] Найдено {len(event_elements)} потенциальных событий")

            for element in event_elements:
                event = self._parse_element(element)
                if event:
                    events.append(event)

            # Если не нашли явных событий, пробуем парсить общую информацию
            if len(events) == 0:
                events = self._parse_general_info(soup)

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
                "h1, h2, h3, h4, .title, .post-title, .project-title, "
                ".news-title, .event-title, [class*='title'], [class*='heading']"
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
                    source_url = f"https://mirahdevelopments.com{href}"
                elif href.startswith("http"):
                    source_url = href
                else:
                    source_url = f"https://mirahdevelopments.com/{href}"
            else:
                source_url = self.SOURCE_URL

            # Для девелоперского сайта определяем тип события по заголовку
            event_type = self._determine_event_type(title)

            # Пытаемся найти дату
            date_el = element.select_one(".date, time, .post-date, .event-date")
            date_text = None
            if date_el:
                date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            
            event_date = self._extract_date_from_text(date_text if date_text else element.get_text())
            if not event_date:
                event_date = date.today()

            # Пытаемся найти описание
            desc_el = element.select_one(
                ".excerpt, .summary, .description, .content, p, "
                "[class*='desc'], [class*='content']"
            )
            description = desc_el.get_text(strip=True)[:500] if desc_el else None

            # Определяем место (скорее всего Бали для этого девелопера)
            location = self._detect_location(element.get_text())

            # Определяем категорию
            category = self._determine_category(title, description)

            # Определяем формат (оффлайн/онлайн)
            is_online = "online" in title.lower() or "webinar" in title.lower()

            return RawEvent(
                title=title[:200],
                event_date=event_date,
                location=location,
                source_url=source_url,
                source_name=self.SOURCE_NAME,
                description=description,
                price=None,
                category=category,
            )

        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка при парсинге элемента: {e}")
            return None

    def _parse_general_info(self, soup) -> list[RawEvent]:
        """
        Если явных событий нет, парсим общую информацию как потенциальные события.
        """
        events = []
        
        try:
            # Ищем разделы с информацией о проектах
            sections = soup.select("section, article, .section, [class*='content']")
            
            for section in sections:
                # Ищем заголовки с ключевыми словами
                headings = section.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
                
                for heading in headings:
                    text = heading.get_text(strip=True)
                    if len(text) > 10 and any(keyword in text.lower() for keyword in 
                                              ["launch", "opening", "presentation", 
                                               "exhibition", "showcase", "event", 
                                               "meeting", "forum", "conference"]):
                        
                        # Ищем ближайший абзац
                        next_p = heading.find_next("p")
                        description = next_p.get_text(strip=True)[:300] if next_p else None
                        
                        # Ищем дату в тексте
                        event_date = self._extract_date_from_text(text + " " + (description or ""))
                        if not event_date:
                            event_date = date.today()
                        
                        event = RawEvent(
                            title=text[:200],
                            event_date=event_date,
                            location=self._detect_location(text + " " + (description or "")),
                            source_url=self.SOURCE_URL,
                            source_name=self.SOURCE_NAME,
                            description=description,
                            price=None,
                            category=self._determine_category(text, description),
                        )
                        events.append(event)
            
        except Exception as e:
            logger.debug(f"[{self.SOURCE_NAME}] Ошибка при парсинге общей информации: {e}")
        
        return events

    def _extract_date_from_text(self, text: str) -> Optional[date]:
        """
        Извлечь дату из текста.
        """
        if not text:
            return None
            
        # Ищем паттерны дат
        patterns = [
            r'(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})',  # DD-MM-YYYY
            r'(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # 15 July 2026
            r'(\w+)\s+(\d{1,2})\s+(\d{4})',  # July 15 2026
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 3:
                        try:
                            # Пробуем распарсить в зависимости от паттерна
                            if pattern == patterns[0]:  # DD-MM-YYYY
                                day, month, year = match.groups()
                                return date(int(year), int(month), int(day))
                            elif pattern == patterns[1]:  # YYYY-MM-DD
                                year, month, day = match.groups()
                                return date(int(year), int(month), int(day))
                            elif pattern in (patterns[2], patterns[3]):  # Month DD YYYY
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
            "kuta", "jimbaran", "uluwatu", "nusa dua", "bukit"
        ]
        
        for district in bali_districts:
            if district in text_lower:
                return district.capitalize() + ", Bali"
        
        # По умолчанию для девелопера на Бали
        return "Bali, Indonesia"

    def _determine_event_type(self, title: str) -> str:
        """
        Определить тип события по заголовку.
        """
        title_lower = title.lower()
        
        if any(word in title_lower for word in ["launch", "opening"]):
            return "launch"
        elif any(word in title_lower for word in ["presentation", "showcase"]):
            return "presentation"
        elif any(word in title_lower for word in ["exhibition", "show"]):
            return "exhibition"
        elif any(word in title_lower for word in ["meeting", "gathering"]):
            return "meeting"
        elif any(word in title_lower for word in ["forum", "conference"]):
            return "conference"
        elif any(word in title_lower for word in ["webinar", "online", "virtual"]):
            return "webinar"
        else:
            return "event"

    def _determine_category(self, title: str, description: Optional[str]) -> str:
        """
        Определить категорию события.
        """
        text = (title + " " + (description or "")).lower()
        
        if any(word in text for word in ["residential", "apartment", "condo", "вилла", "villa"]):
            return "residential"
        elif any(word in text for word in ["commercial", "office", "retail", "офис", "торговый"]):
            return "commercial"
        elif any(word in text for word in ["investment", "investor", "инвестиции", "roi"]):
            return "investment"
        elif any(word in text for word in ["development", "девелопмент", "project", "проект"]):
            return "development"
        else:
            return "property"