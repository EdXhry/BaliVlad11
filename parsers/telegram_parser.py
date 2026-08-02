"""
Парсер Telegram каналов через официальный MTProto API (Telethon).

Требует:
- TELEGRAM_API_ID    — из my.telegram.org
- TELEGRAM_API_HASH  — из my.telegram.org
- TELEGRAM_PHONE     — номер телефона аккаунта (для первой авторизации)

Сессия сохраняется в файл telegram_session.session — повторная авторизация
не нужна, пока файл существует.
"""
import asyncio
import logging
import os
import re
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    FloodWaitError,
)
from telethon.tl.types import Message, Channel

from parsers.base import RawEvent

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Настройки из .env ────────────────────────────────────────────────────────
_api_id_raw = os.getenv("TELEGRAM_API_ID", "0")
API_ID   = int(_api_id_raw) if _api_id_raw.isdigit() else 0
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE    = os.getenv("TELEGRAM_PHONE", "")

# Файл сессии — хранит авторизацию, не нужно входить каждый раз
SESSION_FILE = "telegram_session"

# Сколько последних сообщений брать из канала
DEFAULT_LIMIT = 50


class TelegramApiParser:
    """
    Парсер одного Telegram канала через MTProto API.

    Использование:
        parser = TelegramApiParser("bali_invest")
        events = parser.parse()   # синхронный вызов, внутри запускает asyncio
        parser.close()
    """

    def __init__(self, username: str, limit: int = DEFAULT_LIMIT):
        self.username = username.lstrip("@")
        self.source_name = f"Telegram: @{self.username}"
        self.limit = limit

        if not API_ID or not API_HASH:
            raise ValueError(
                "TELEGRAM_API_ID и TELEGRAM_API_HASH не заданы в .env!\n"
                "Получи их на https://my.telegram.org"
            )

    # ── Публичный синхронный интерфейс (совместим с BaseParser) ──────────────

    def parse(self) -> List[RawEvent]:
        """Запустить парсинг (синхронный враппер над async логикой)."""
        try:
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(self._parse_async())
        except Exception as e:
            logger.error(f"[{self.source_name}] Ошибка парсинга: {e}", exc_info=True)
            return []
        finally:
            loop.close()

    def close(self):
        """Совместимость с интерфейсом BaseParser — ничего не делает,
        клиент создаётся и закрывается внутри каждого вызова parse()."""
        pass

    # ── Async логика ──────────────────────────────────────────────────────────

    async def _parse_async(self) -> List[RawEvent]:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        await client.connect()

        # Если сессия есть — авторизация не нужна
        if not await client.is_user_authorized():
            logger.error(
                f"[{self.source_name}] Клиент не авторизован. "
                "Запусти venv\\Scripts\\python.exe init_telegram_session.py "
                "для первичной авторизации."
            )
            await client.disconnect()
            return []

        try:
            logger.info(f"[{self.source_name}] Получаю сообщения из @{self.username}")
            events = await self._fetch_messages(client)
            logger.info(f"[{self.source_name}] Получено {len(events)} событий")
            return events

        except ChannelPrivateError:
            logger.error(f"[{self.source_name}] Канал @{self.username} приватный или недоступен")
        except (UsernameInvalidError, UsernameNotOccupiedError):
            logger.error(f"[{self.source_name}] Канал @{self.username} не существует")
        except FloodWaitError as e:
            logger.warning(f"[{self.source_name}] FloodWait: нужно подождать {e.seconds} сек.")
        except Exception as e:
            logger.error(f"[{self.source_name}] Неожиданная ошибка: {e}", exc_info=True)
        finally:
            await client.disconnect()

        return []

    async def _fetch_messages(self, client: TelegramClient) -> List[RawEvent]:
        """Получить и распарсить сообщения канала."""
        entity = await client.get_entity(self.username)
        messages = await client.get_messages(entity, limit=self.limit)

        events = []
        for msg in messages:
            event = self._parse_message(msg)
            if event:
                events.append(event)

        return events

    def _parse_message(self, msg: Message) -> Optional[RawEvent]:
        """Преобразовать одно сообщение Telegram в RawEvent."""
        try:
            # Пропускаем сообщения без текста (фото без подписи и т.д.)
            if not msg.message or len(msg.message.strip()) < 10:
                return None

            text = msg.message.strip()

            # Дата сообщения (aware datetime → date)
            msg_date: date = msg.date.astimezone(timezone.utc).date()

            # Пробуем извлечь дату события из текста
            event_date = self._extract_date(text)
            
            # Если дата не найдена в тексте — ставим завтра (чтобы не отфильтровалось)
            if not event_date:
                event_date = date.today() + timedelta(days=1)

            # Ссылка на сообщение
            source_url = f"https://t.me/{self.username}/{msg.id}"

            return RawEvent(
                title=self._extract_title(text),
                event_date=event_date,
                location=self._detect_location(text),
                source_url=source_url,
                source_name=self.source_name,
                description=text[:500],
                price=self._extract_price(text),
                category=self._detect_category(text),
                speakers=self._extract_speakers(text),
                language=self._detect_language(text),
                is_online=self._is_online(text),
                event_type=self._detect_event_type(text),
            )

        except Exception as e:
            logger.debug(f"[{self.source_name}] Ошибка при парсинге сообщения {msg.id}: {e}")
            return None

    # ── Вспомогательные методы анализа текста ────────────────────────────────

    def _extract_title(self, text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if lines and len(lines[0]) >= 10:
            return lines[0][:200]
        sentences = re.split(r"[.!?]", text)
        if sentences and sentences[0].strip():
            return sentences[0].strip()[:200]
        return text[:200]

    def _extract_date(self, text: str) -> Optional[date]:
        ru_months = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
        }
        en_months = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        patterns = [
            # DD.MM.YYYY  /  DD-MM-YYYY  /  DD/MM/YYYY
            (r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", "dmy"),
            # YYYY-MM-DD
            (r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", "ymd"),
            # 15 июля 2026  /  15 july 2026
            (r"(\d{1,2})\s+([а-яёa-z]+)\s+(\d{4})", "d_month_y"),
        ]

        for pattern, fmt in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    g = m.groups()
                    if fmt == "dmy":
                        d, mo, y = int(g[0]), int(g[1]), int(g[2])
                    elif fmt == "ymd":
                        y, mo, d = int(g[0]), int(g[1]), int(g[2])
                    else:  # d_month_y
                        d = int(g[0])
                        month_str = g[1].lower()
                        mo = ru_months.get(month_str) or en_months.get(month_str)
                        if not mo:
                            continue
                        y = int(g[2])

                    if 1 <= mo <= 12 and 1 <= d <= 31 and 2020 <= y <= 2035:
                        return date(y, mo, d)
                except (ValueError, TypeError):
                    continue
        return None

    def _detect_location(self, text: str) -> str:
        text_lower = text.lower()
        districts = [
            "denpasar", "canggu", "ubud", "seminyak", "sanur",
            "kuta", "jimbaran", "uluwatu", "nusa dua", "bukit",
            "nusa lembongan", "nusa penida", "bedugul", "lovina", "amed",
        ]
        for d in districts:
            if d in text_lower:
                return d.title() + ", Bali"
        if any(w in text_lower for w in ["bali", "бали"]):
            return "Bali, Indonesia"
        if self._is_online(text):
            return "Online"
        return "Bali, Indonesia"

    def _is_online(self, text: str) -> bool:
        text_lower = text.lower()
        return any(w in text_lower for w in [
            "online", "онлайн", "webinar", "вебинар",
            "zoom", "stream", "стрим", "трансляция", "virtual",
        ])

    def _extract_price(self, text: str) -> Optional[str]:
        patterns = [
            r"\$[\d,]+(?:\.\d{2})?",
            r"\d[\d,]*\s*(?:USD|EUR|IDR|RUB)",
            r"\d[\d,]*\s*k?\s*IDR",
            r"free\b",
            r"бесплатно",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(0)[:50]
        return None

    def _extract_speakers(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:спикер[ы]?:?)\s*([^\n.]+)",
            r"(?:speaker[s]?:?)\s*([^\n.]+)",
            r"(?:ведущий:?)\s*([^\n.]+)",
            r"(?:presenter:?)\s*([^\n.]+)",
            r"(?:модератор:?)\s*([^\n.]+)",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()[:100]
        return None

    def _detect_language(self, text: str) -> str:
        has_cyrillic = bool(re.search(r"[а-яА-ЯёЁ]", text))
        has_latin    = bool(re.search(r"[a-zA-Z]", text))
        if has_cyrillic and has_latin:
            return "ru+en"
        if has_cyrillic:
            return "ru"
        if has_latin:
            return "en"
        return "unknown"

    def _detect_event_type(self, text: str) -> str:
        text_lower = text.lower()
        mapping = [
            (["конференци", "conference"],           "conference"),
            (["форум", "forum"],                     "forum"),
            (["митап", "meetup", "встреча", "meet"], "meetup"),
            (["выставка", "exhibition", "expo"],     "exhibition"),
            (["семинар", "вебинар", "webinar", "seminar"], "seminar"),
            (["воркшоп", "workshop"],                "workshop"),
        ]
        for keywords, etype in mapping:
            if any(k in text_lower for k in keywords):
                return etype
        return "event"

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        keywords = [
            "property", "real estate", "недвижимость", "инвестиц",
            "development", "villa", "вилла", "apartment", "апартамент",
            "land", "участок", "аренда", "rent", "coliving", "strata",
            "roi", "yield", "девелопмент", "строительств",
        ]
        if any(k in text_lower for k in keywords):
            return "property"
        return "other"
