"""
Формирование дайджеста — plain text (HTML mode).

Структура дайджеста:
  1. Заголовок
  2. Блок «🏝 ОФФЛАЙН — БАЛИ» — живые мероприятия на острове, сортировка по дате
  3. Блок «🌍 ОНЛАЙН — ВЕСЬ МИР (RU)» — русскоязычные онлайн-ивенты, сортировка по дате
  4. Итоговая строка
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import storage

logger = logging.getLogger(__name__)

WITA_OFFSET = timedelta(hours=8)

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
DAYS_RU = {
    0: "пн", 1: "вт", 2: "ср",
    3: "чт", 4: "пт", 5: "сб", 6: "вс",
}
EVENT_TYPE_RU = {
    "forum":      "форум",
    "conference": "конференция",
    "meetup":     "встреча/митап",
    "exhibition": "выставка",
    "seminar":    "семинар",
    "event":      "мероприятие",
}
LANG_DISPLAY = {
    "ru":    "🇷🇺 RU",
    "en":    "🇬🇧 EN",
    "ru+en": "🇷🇺🇬🇧 RU+EN",
}


def compile_digest(days: int = 7) -> Optional[str]:
    """
    Собрать дайджест событий добавленных за последние days дней.
    Разбит на два блока: оффлайн Бали и онлайн весь мир.
    Возвращает HTML-текст для parse_mode='HTML' или None если событий нет.
    """
    events = storage.get_recently_added_events(days=days)
    if not events:
        logger.info("Нет событий для дайджеста")
        return None

    logger.info(f"Формирую дайджест: {len(events)} событий")

    # Разделяем на два потока:
    # - bali + НЕ онлайн → блок Бали оффлайн
    # - world ИЛИ is_online → блок онлайн (только если язык RU)
    bali_offline = [
        ev for ev in events
        if ev.get("source_geo", "bali") == "bali" and not ev.get("is_online")
    ]
    world_online = [
        ev for ev in events
        if ev.get("source_geo", "bali") == "world"
        or (ev.get("source_geo", "bali") == "bali" and ev.get("is_online"))
    ]
    # Онлайн из балийских источников — только RU по ТЗ
    world_online = [
        ev for ev in world_online
        if ev.get("language") in ("ru", "ru+en")
    ]

    # Сортируем каждый блок по дате
    bali_offline.sort(key=lambda x: x["event_date"])
    world_online.sort(key=lambda x: x["event_date"])

    # Если совсем нет ни одного события — None
    if not bali_offline and not world_online:
        return None

    lines = [
        "<b>📅 Дайджест: инвестиции и недвижимость</b>",
        f"<i>Новое за {days} дней</i>",
        "",
    ]

    # ── Блок 1: Оффлайн Бали ──────────────────────────────────────────────
    if bali_offline:
        lines.append("🏝 <b>ОФФЛАЙН — БАЛИ</b>")
        lines.append("─" * 20)
        lines.append("")
        for ev in bali_offline:
            lines.append(_fmt_event(ev))
            lines.append("")
    else:
        lines.append("🏝 <b>ОФФЛАЙН — БАЛИ</b>")
        lines.append("─" * 20)
        lines.append("<i>Мероприятий не найдено</i>")
        lines.append("")

    # ── Блок 2: Онлайн весь мир ───────────────────────────────────────────
    if world_online:
        lines.append("🌍 <b>ОНЛАЙН — ВЕСЬ МИР (RU)</b>")
        lines.append("─" * 20)
        lines.append("")
        for ev in world_online:
            lines.append(_fmt_event(ev))
            lines.append("")
    else:
        lines.append("🌍 <b>ОНЛАЙН — ВЕСЬ МИР (RU)</b>")
        lines.append("─" * 20)
        lines.append("<i>Мероприятий не найдено</i>")
        lines.append("")

    # ── Итог ─────────────────────────────────────────────────────────────
    total = len(bali_offline) + len(world_online)
    lines.append(
        f"<i>Найдено {total} новых событий за {days} дней "
        f"({len(bali_offline)} на Бали, {len(world_online)} онлайн)</i>"
    )

    text = "\n".join(lines).strip()

    # Telegram limit 4096
    if len(text) > 4000:
        text = text[:3950] + "\n\n<i>...и ещё события. Смотри все в канале.</i>"

    return text


def _fmt_event(ev: Dict[str, Any]) -> str:
    lines = []

    # 📅 Дата и время
    t_str = ev.get("event_time")
    date_str = _fmt_date(ev["event_date"])
    if t_str and str(t_str) not in ("None", "null", ""):
        try:
            from datetime import time as dtime
            parts = str(t_str).split(":")
            t    = dtime(int(parts[0]), int(parts[1]))
            dt   = datetime.combine(ev["event_date"], t)
            wita = (dt + WITA_OFFSET).strftime("%H:%M")
            lines.append(f"📅 {date_str}, <i>{wita} WITA</i>")
        except Exception:
            lines.append(f"📅 {date_str}, <i>время уточняется</i>")
    else:
        lines.append(f"📅 {date_str}, <i>время уточняется</i>")

    # 📍 Место
    if ev.get("is_online"):
        platform = _detect_platform(ev.get("description") or "")
        lines.append(f"📍 <b>Онлайн (RU)</b> — {_h(platform)}")
    else:
        location = ev.get("location", "Bali")
        lines.append(f"📍 <b>{_h(location)}</b>")

    # 🏷 Тип мероприятия
    etype = EVENT_TYPE_RU.get(ev.get("event_type") or "event", "мероприятие")
    lines.append(f"🏷 {_h(etype)}")

    # 🧵 Название
    title = ev.get("title", "")
    if len(title) > 120:
        title = title[:120] + "..."
    lines.append(f"🧵 <b>{_h(title)}</b>")

    # 🗣 Спикеры + Язык
    row = []
    if ev.get("speakers"):
        sp = ev["speakers"]
        if len(sp) > 80:
            sp = sp[:80] + "..."
        row.append(f"🗣 {_h(sp)}")
    lang_str = LANG_DISPLAY.get(ev.get("language") or "", "")
    if lang_str:
        row.append(f"Язык: {lang_str}")
    if row:
        lines.append("  ".join(row))

    # 🔗 Ссылка
    url = ev.get("source_url", "")
    if url and url.startswith("http"):
        lines.append(f'🔗 <a href="{url}">Подробнее</a>')
    elif ev.get("source_name"):
        lines.append(f"📰 {_h(ev['source_name'])}")

    return "\n".join(lines)


def _fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_RU[d.month]} ({DAYS_RU[d.weekday()]})"


def _detect_platform(text: str) -> str:
    t = text.lower()
    if "zoom" in t:      return "Zoom"
    if "youtube" in t:   return "YouTube Live"
    if "telegram" in t:  return "Telegram"
    if "teams" in t:     return "MS Teams"
    if "meet" in t:      return "Google Meet"
    return "онлайн-платформа"


def _h(text: str) -> str:
    """Экранировать HTML-спецсимволы."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
