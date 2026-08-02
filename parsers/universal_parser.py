"""
Универсальный парсер для всех источников.
Использует конфигурационные файлы для определения правил парсинга.
"""
import logging
import re
import yaml
from datetime import date, datetime, time, timedelta
from typing import Optional, Dict, List, Any, Tuple
from bs4 import BeautifulSoup
from parsers.base import BaseParser, RawEvent

logger = logging.getLogger(__name__)


class ParsingRules:
    """
    Конфигурация правил парсинга для источника.
    """
    def __init__(self, config: Dict[str, Any]):
        self.event_selector = config.get("event_selector", "article, .post, .card")
        self.title_selector = config.get("title_selector", "h1, h2, h3, h4, .title")
        self.date_selector = config.get("date_selector", "time, .date, [class*='date']")
        self.location_selector = config.get("location_selector", ".location, .place, .address")
        self.description_selector = config.get("description_selector", ".excerpt, .summary, p")
        self.price_selector = config.get("price_selector", ".price, .amount, .cost")
        self.link_selector = config.get("link_selector", "a[href]")
        self.content_selector = config.get("content_selector", "")  # для Telegram
        
        # Дополнительные настройки
        self.date_format = config.get("date_format", "auto")
        self.default_location = config.get("default_location", "Bali, Indonesia")
        
        # Языковые настройки
        self.language_hint = config.get("language_hint", "")  # ru, en, или оба


class UniversalParser(BaseParser):
    """
    Универсальный парсер, который может работать с разными источниками
    на основе конфигурационных правил.
    """
    
    def __init__(self, source_name: str, url: str, parsing_rules: Dict[str, Any], 
                 source_type: str = "website"):
        super().__init__()
        self.source_name = source_name
        self.url = url
        self.source_type = source_type
        self.rules = ParsingRules(parsing_rules)
        
        # Кэш для найденных событий
        self._cached_html = None
        
        logger.info(f"[{source_name}] Инициализирован парсер для {url} ({source_type})")

    def parse(self) -> List[RawEvent]:
        """
        Основной метод парсинга.
        """
        logger.info(f"[{self.source_name}] Парсинг {self.url}")

        events = []

        try:
            if self.source_type == "telegram":
                events = self._parse_telegram_api()
            elif self.source_type == "website":
                events = self._parse_website()
            else:
                logger.warning(f"Неизвестный тип источника: {self.source_type}")
                return []

        except Exception as e:
            logger.error(f"[{self.source_name}] Ошибка парсинга: {e}", exc_info=True)
            return []

        logger.info(f"[{self.source_name}] Найдено {len(events)} событий")
        return events
    
    def _parse_telegram_api(self) -> List[RawEvent]:
        """
        Парсинг Telegram канала через официальный MTProto API (Telethon).
        Требует авторизованной сессии — см. init_telegram_session.py.
        """
        from parsers.telegram_parser import TelegramApiParser
        parser = TelegramApiParser(self.url)
        return parser.parse()

    def _parse_website(self) -> List[RawEvent]:
        """
        Парсинг веб-сайтов с использованием CSS-селекторов.
        """
        try:
            response = self._get(self.url)
        except Exception as e:
            # 403, таймаут и прочее — молча возвращаем пустой список
            logger.warning(f"[{self.source_name}] Ошибка парсинга: {type(e).__name__} — пропускаем")
            return []

        soup = BeautifulSoup(response.text, "lxml")
        
        events = []
        
        # Находим все элементы событий
        event_elements = soup.select(self.rules.event_selector)
        logger.debug(f"[{self.source_name}] Найдено {len(event_elements)} потенциальных событий")
        
        for element in event_elements:
            event = self._parse_website_element(element)
            if event:
                events.append(event)
        
        return events
    
    def _parse_website_element(self, element) -> Optional[RawEvent]:
        """
        Извлечь данные о событии из HTML элемента веб-сайта.
        """
        try:
            # Извлекаем заголовок
            title = self._extract_field(element, self.rules.title_selector)
            if not title or len(title) < 3:
                return None
            
            # Извлекаем ссылку
            source_url = self._extract_link(element, self.rules.link_selector)
            if not source_url:
                source_url = self.url
            
            # Извлекаем дату
            event_date = self._extract_date(element)
            
            # Извлекаем место
            location = self._extract_location(element)
            
            # Извлекаем описание
            description = self._extract_field(element, self.rules.description_selector)
            if description:
                description = description[:500]  # Ограничиваем длину
            
            # Извлекаем цену
            price = self._extract_field(element, self.rules.price_selector)
            
            # Определяем категорию по содержанию
            category = self._detect_category(element.get_text(), title)
            
            return RawEvent(
                title=title[:200],  # Ограничиваем длину
                event_date=event_date,
                location=location,
                source_url=source_url,
                source_name=self.source_name,
                description=description,
                price=price,
                category=category,
            )
            
        except Exception as e:
            logger.debug(f"[{self.source_name}] Ошибка при парсинге элемента: {e}")
            return None
    
    def _extract_field(self, element, selector: str) -> Optional[str]:
        """Извлечь текст по CSS-селектору."""
        if not selector:
            return None
            
        selected = element.select_one(selector)
        if selected:
            return selected.get_text(strip=True)
        return None
    
    def _extract_link(self, element, selector: str) -> Optional[str]:
        """Извлечь ссылку по CSS-селектору."""
        if not selector:
            return None
            
        link_el = element.select_one(selector)
        if link_el and link_el.get("href"):
            href = link_el.get("href")
            if href.startswith("/"):
                return f"{self.url}{href}"
            elif href.startswith("http"):
                return href
            else:
                return f"{self.url}/{href}"
        return None
    
    def _extract_date(self, element) -> date:
        """Извлечь дату из элемента."""
        # Пробуем по селектору
        date_text = self._extract_field(element, self.rules.date_selector)
        if date_text:
            parsed_date = self._parse_date_string(date_text)
            if parsed_date:
                return parsed_date
        
        # Пробуем из всего текста элемента
        all_text = element.get_text()
        parsed_date = self._extract_date_from_text(all_text)
        if parsed_date:
            return parsed_date
        
        # По умолчанию - завтра (чтобы не отфильтровались как "прошедшие")
        return date.today() + timedelta(days=1)
    
    def _extract_location(self, element) -> str:
        """Извлечь место из элемента."""
        # Пробуем по селектору
        location = self._extract_field(element, self.rules.location_selector)
        if location:
            return location
        
        # Пробуем определить из текста
        all_text = element.get_text()
        detected = self._detect_location(all_text)
        if detected != "Bali, Indonesia":
            return detected
        
        # По умолчанию
        return self.rules.default_location
    
    def _extract_title_from_telegram(self, text: str) -> str:
        """Извлечь заголовок из текста Telegram поста."""
        # Первые несколько слов как заголовок
        words = text.split()
        if len(words) <= 10:
            return text[:100]
        
        # Ищем первое предложение
        sentences = re.split(r'[.!?]', text)
        if sentences and sentences[0].strip():
            return sentences[0].strip()[:100]
        
        # Первые 10 слов
        return " ".join(words[:10])[:100]
    
    def _extract_price_from_text(self, text: str) -> Optional[str]:
        """Извлечь цену из текста."""
        # Ищем паттерны цен: $100, 100 USD, 100k IDR и т.д.
        patterns = [
            r'(\$[\d,]+(?:\.\d{2})?)',  # $100, $1,000
            r'(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|IDR|RUB))',  # 100 USD
            r'(\d+(?:,\d{3})*\s*k?\s*IDR)',  # 100k IDR
            r'(цена:\s*\d+)',  # цена: 100
            r'(\d+\s*\$)',  # 100 $
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)[:50]
        
        return None
    
    def _extract_speakers(self, text: str) -> Optional[str]:
        """
        Извлечь имена спикеров из текста.
        Ищет паттерны: "Speaker:", "Спикер:", имена в начале строк и т.д.
        """
        # Паттерны для поиска спикеров
        speaker_patterns = [
            r'(?:Спикер[ы]?:?)\s*([^\.\n]+)',
            r'(?:Speaker[s]?:?)\s*([^\.\n]+)',
            r'(?:Ведущий:?)\s*([^\.\n]+)',
            r'(?:Presenter:?)\s*([^\.\n]+)',
            r'(?:Модератор:?)\s*([^\.\n]+)',
        ]
        
        for pattern in speaker_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                speakers = match.group(1).strip()
                # Ограничиваем длину
                if len(speakers) > 100:
                    speakers = speakers[:100] + "..."
                return speakers
        
        return None
    
    def _detect_category(self, text: str, title: str) -> str:
        """Определить категорию события по тексту."""
        text_lower = text.lower()
        title_lower = title.lower()
        
        # Ключевые слова для категорий недвижимости (по ТЗ)
        property_keywords = [
            "property", "real estate", "недвижимость", "инвестиция", "инвестиции",
            "development", "разработка", "строительство", "продажа", "аренда",
            "apartment", "villa", "вилла", "апартаменты", "house", "дом",
            "land", "участок", "коммерческая", "commercial", "residential", "жилая"
        ]
        
        for keyword in property_keywords:
            if keyword in text_lower or keyword in title_lower:
                return "property"
        
        return "other"
    
    def _detect_location(self, text: str) -> str:
        """Определить место проведения из текста."""
        text_lower = text.lower()
        
        # Районы Бали по ТЗ
        bali_districts = [
            "bali", "denpasar", "canggu", "ubud", "seminyak", "sanur",
            "kuta", "jimbaran", "uluwatu", "nusa dua", "bukit",
            "nusa lembongan", "nusa penida", "tegalalang", "tegallalang", "bedugul",
            "lovina", "amed", "tanah lot"
        ]
        
        for district in bali_districts:
            if district in text_lower:
                return district.capitalize() + ", Bali"
        
        return "Bali, Indonesia"
    
    def _extract_date_from_text(self, text: str) -> Optional[date]:
        """Извлечь дату из текста."""
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
                        # Определяем формат даты
                        if pattern == patterns[0]:  # DD-MM-YYYY
                            day, month, year = map(int, match.groups())
                        elif pattern == patterns[1]:  # YYYY-MM-DD
                            year, month, day = map(int, match.groups())
                        elif pattern in (patterns[2], patterns[3], patterns[4]):  # Month DD YYYY
                            # Определяем месяц по имени
                            month_names = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                                'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                                'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            
                            groups = list(match.groups())
                            month = None
                            for i, g in enumerate(groups):
                                if g.lower() in month_names:
                                    month = month_names[g.lower()]
                                    del groups[i]
                                    break
                            
                            if month and len(groups) == 2:
                                nums = [int(g) for g in groups]
                                day = min(nums)
                                year = max(nums)
                                if year < 100:
                                    year += 2000
                            else:
                                continue
                        else:
                            continue
                        
                        return date(year, month, day)
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """Парсинг строки с датой."""
        try:
            # Пробуем стандартные форматы
            formats = [
                "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d",
                "%d.%m.%Y", "%Y.%m.%d", "%d %B %Y", "%B %d %Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except ValueError:
                    continue
        except Exception:
            pass
        
        return None


class ParserFactory:
    """
    Фабрика для создания парсеров на основе конфигурации.
    """
    
    def __init__(self, config_path: str = "source_configs.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузить конфигурацию из YAML файла."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Конфигурационный файл {self.config_path} не найден")
            return {}
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return {}
    
    def create_parser(self, source_config: Dict[str, Any]) -> Optional[UniversalParser]:
        """
        Создать парсер на основе конфигурации источника.
        """
        try:
            name = source_config.get("name", "Unknown Source")
            url = source_config.get("url", "")
            source_type = source_config.get("type", "website")
            
            if not url:
                logger.error(f"Источник '{name}' не имеет URL")
                return None
            
            # Определяем правила парсинга
            if source_type == "telegram":
                parsing_rules = self._get_telegram_rules()
            else:
                # Пробуем найти правила для конкретного сайта
                parsing_rules = self._get_website_rules(name, url)
            
            return UniversalParser(name, url, parsing_rules, source_type)
            
        except Exception as e:
            logger.error(f"Ошибка создания парсера: {e}")
            return None
    
    def _get_telegram_rules(self) -> Dict[str, Any]:
        """Получить правила парсинга для Telegram."""
        telegram_config = self.config.get("telegram", {})
        return {
            "content_selector": telegram_config.get("content_selector", ".tgme_widget_message_text"),
            "date_format": "telegram",
            "default_location": "Online / Bali, Indonesia",
        }
    
    def _get_website_rules(self, name: str, url: str) -> Dict[str, Any]:
        """Получить правила парсинга для вебсайта."""
        # Пробуем найти конкретные правила для сайта
        sources_config = self.config.get("sources", {})
        
        # Определяем по имени или URL
        site_key = None
        for key, config in sources_config.items():
            if isinstance(config, dict):
                if config.get("name") == name or config.get("url") == url:
                    site_key = key
                    break
        
        if site_key:
            # Используем конкретные правила
            site_config = sources_config[site_key]
            return site_config.get("parsing_rules", {})
        else:
            # Используем правила по умолчанию
            default_config = sources_config.get("default_website", {})
            return default_config.get("parsing_rules", {})