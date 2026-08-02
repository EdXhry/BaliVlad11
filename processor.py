"""
Обработчик сырых событий: фильтрация по ТЗ + сохранение в JSON-хранилище.

Правила:
  Оффлайн → явно Бали + тема + (RU или EN)
  Онлайн  → тема + только RU (ru или ru+en)
  Исключить: вебинары, юр/миграция, мастер-классы, оффлайн не-Бали
"""
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from config import (
    is_relevant_topic, is_bali_location, is_online,
    detect_language, extract_event_type, extract_speakers,
)
import storage

logger = logging.getLogger(__name__)

CATEGORY_EMOJI = {
    "investment":  "💰",
    "property":    "🏠",
    "development": "🏗️",
    "management":  "📊",
    "coliving":    "👥",
}


def process_events(raw_events: list) -> dict:
    """
    Обработать список сырых событий.
    raw_events — список RawEvent или dict.
    Возвращает статистику.
    """
    stats = {
        "saved": 0,
        "invalid": 0,
        "duplicates": 0,
        "filtered_topic": 0,
        "filtered_geo": 0,
        "filtered_language": 0,
        "errors": 0,
    }

    for raw in raw_events:
        result = _process_one(raw)
        if result in stats:
            stats[result] += 1
        else:
            stats["errors"] += 1

    logger.info(
        f"Обработка: сохр={stats['saved']} "
        f"тема={stats['filtered_topic']} "
        f"гео={stats['filtered_geo']} "
        f"язык={stats['filtered_language']} "
        f"дубл={stats['duplicates']} "
        f"ошибки={stats['errors']}"
    )
    return stats


def _process_one(raw) -> str:
    try:
        # Нормализуем в dict
        if hasattr(raw, "__dict__"):
            d = {
                "title":       getattr(raw, "title", ""),
                "event_date":  getattr(raw, "event_date", None),
                "location":    getattr(raw, "location", ""),
                "source_url":  getattr(raw, "source_url", ""),
                "source_name": getattr(raw, "source_name", ""),
                "description": getattr(raw, "description", None),
                "price":       getattr(raw, "price", None),
                "speakers":    getattr(raw, "speakers", None),
                "language":    getattr(raw, "language", None),
                "is_online":   getattr(raw, "is_online", None),
                "event_type":  getattr(raw, "event_type", None),
                "category":    getattr(raw, "category", None),
                "event_time":  str(getattr(raw, "event_time", None)),
                "source_geo":  getattr(raw, "source_geo",
                                raw.__dict__.get("source_geo", "bali")),
            }
        else:
            d = dict(raw)

        # ── 1. Валидация ───────────────────────────────────────────────────
        err = _validate(d)
        if err:
            logger.debug(f"[invalid] '{d.get('title', '')[:50]}': {err}")
            return "invalid"

        full_text = f"{d['title']} {d.get('description') or ''} {d['location']}"

        # ── 2. Тема — обязательна для ВСЕХ источников ────────────────────
        if not is_relevant_topic(full_text):
            logger.debug(f"[topic] '{d['title'][:60]}'")
            return "filtered_topic"

        # ── 3. Онлайн/оффлайн — определяем по geo источника ──────────────
        source_geo = d.get("source_geo", "bali")
        if source_geo == "world":
            # Источники ЮАР/мир → всегда онлайн (RU worldwide по ТЗ)
            event_is_online = True
        else:
            # Источники Бали → проверяем текст, по умолчанию оффлайн
            event_is_online = d.get("is_online")
            if event_is_online is None:
                event_is_online = is_online(full_text)

        # ── 4. Гео — только для оффлайн ───────────────────────────────────
        if not event_is_online:
            if not is_bali_location(f"{d['location']} {d.get('description') or ''}"):
                logger.debug(f"[geo] '{d['title'][:60]}'")
                return "filtered_geo"

        # ── 5. Язык — онлайн только RU, оффлайн RU+EN ────────────────────
        lang = d.get("language") or detect_language(full_text)
        if event_is_online:
            # Онлайн блок строго только русский язык по ТЗ
            if lang not in ("ru", "ru+en"):
                logger.debug(f"[lang] online non-RU: lang={lang} '{d['title'][:50]}'")
                return "filtered_language"
        else:
            # Оффлайн Бали — RU или EN, unknown отфильтровываем
            if lang == "unknown":
                logger.debug(f"[lang] unknown: '{d['title'][:60]}'")
                return "filtered_language"

        # ── 6. Метаданные ─────────────────────────────────────────────────
        event_type = d.get("event_type") or extract_event_type(full_text)
        speakers   = d.get("speakers") or extract_speakers(full_text)
        category   = d.get("category") or _determine_category(full_text)

        # ── 7. Сохранение ─────────────────────────────────────────────────
        record = {
            "title":       d["title"],
            "event_date":  str(d["event_date"]),
            "event_time":  d.get("event_time"),
            "location":    d["location"],
            "source_url":  d["source_url"],
            "source_name": d["source_name"],
            "description": (d.get("description") or "")[:500],
            "price":       d.get("price"),
            "category":    category,
            "language":    lang,
            "event_type":  event_type,
            "speakers":    speakers,
            "is_online":   event_is_online,
            "source_geo":  source_geo,
        }

        is_new = storage.save_event(record)
        if not is_new:
            return "duplicates"

        logger.info(f"[saved] {'🌐' if event_is_online else '📍'} '{d['title'][:70]}' {lang} [{source_geo}]")
        return "saved"

    except Exception as e:
        logger.error(f"[error] {e}", exc_info=True)
        return "errors"


def _validate(d: dict) -> Optional[str]:
    title = d.get("title", "")
    if not title or len(title.strip()) < 5:
        return "title too short"
    if len(title) > 200:
        return "title too long"
    if not d.get("event_date"):
        return "no date"
    try:
        ev_date = date.fromisoformat(str(d["event_date"]))
        today = date.today()
        # ТЗ: «Новое за 24 ч» — события начиная с сегодня и до 31 дня вперёд
        if ev_date < today:
            return f"past ({ev_date})"
        if ev_date > today + timedelta(days=31):
            return f"too far future ({ev_date})"
    except Exception:
        return "bad date"
    if not d.get("location", "").strip():
        return "no location"
    return None


def _determine_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("roi", "yield", "инвестиц", "investment")):
        return "investment"
    if any(k in t for k in ("property management", "управление недвижимост")):
        return "management"
    if any(k in t for k in ("development", "девелопмент", "девелопер")):
        return "development"
    if any(k in t for k in ("coliving", "страта", "strata")):
        return "coliving"
    return "property"
