"""
JSON-хранилище событий и истории публикаций.

Полная замена PostgreSQL — никаких зависимостей кроме стандартной библиотеки.
Все данные хранятся в папке data/:
  data/events.json       — собранные события (дедупликация на лету)
  data/history.json      — история публикаций
  data/stats.json        — статистика запусков

Формат events.json:
  { "<key>": { title, event_date, location, source_url, source_name,
               language, event_type, speakers, is_online, category,
               description, price, created_at }, ... }
  key = md5(source_name + title + event_date)
"""
import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR       = os.path.join(os.path.dirname(__file__), "data")
EVENTS_FILE    = os.path.join(DATA_DIR, "events.json")
HISTORY_FILE   = os.path.join(DATA_DIR, "history.json")
STATS_FILE     = os.path.join(DATA_DIR, "stats.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load(path: str) -> Any:
    _ensure_dir()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return {}


def _save(path: str, data: Any):
    _ensure_dir()
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)  # атомарная замена
    except Exception as e:
        logger.error(f"Ошибка записи {path}: {e}")


# ─── Ключ дедупликации ────────────────────────────────────────────────────────

def _event_key(source_name: str, title: str, event_date: str) -> str:
    raw = f"{source_name}|{title.strip().lower()}|{event_date}"
    return hashlib.md5(raw.encode()).hexdigest()


# ─── События ─────────────────────────────────────────────────────────────────

def save_event(event: Dict[str, Any]) -> bool:
    """
    Сохранить событие. Возвращает True если новое, False если дубликат.
    """
    events = _load(EVENTS_FILE)
    key = _event_key(
        event.get("source_name", ""),
        event.get("title", ""),
        str(event.get("event_date", "")),
    )
    if key in events:
        return False  # дубликат

    events[key] = {**event, "created_at": datetime.utcnow().isoformat()}
    _save(EVENTS_FILE, events)
    return True


def get_upcoming_events(days: int = 7) -> List[Dict[str, Any]]:
    """Вернуть предстоящие события на следующие N дней."""
    events = _load(EVENTS_FILE)
    today    = date.today()
    end_date = today + timedelta(days=days)
    result   = []

    for ev in events.values():
        try:
            ev_date = date.fromisoformat(str(ev.get("event_date", "")))
            if today <= ev_date <= end_date:
                result.append({**ev, "event_date": ev_date})
        except (ValueError, TypeError):
            continue

    result.sort(key=lambda x: x["event_date"])
    return result


def get_recently_added_events(days: int = 7) -> List[Dict[str, Any]]:
    """
    Вернуть события добавленные за последние N дней.
    Сортировка по дате добавления (created_at), от новых к старым.
    """
    events = _load(EVENTS_FILE)
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = []

    for ev in events.values():
        try:
            created_at_str = ev.get("created_at", "")
            if not created_at_str:
                continue
            created_at = datetime.fromisoformat(created_at_str)
            if created_at >= cutoff:
                # Парсим event_date для сортировки
                try:
                    ev_date = date.fromisoformat(str(ev.get("event_date", "")))
                    result.append({**ev, "event_date": ev_date})
                except (ValueError, TypeError):
                    # Если дата события невалидна, всё равно добавляем
                    result.append(ev)
        except (ValueError, TypeError):
            continue

    # Сортируем по дате события (а не по дате добавления)
    result.sort(key=lambda x: x.get("event_date", date.min))
    return result


def get_events_last_week() -> List[Dict[str, Any]]:
    """Вернуть события за последние 7 дней (для /digest в боте)."""
    return get_recently_added_events(days=7)


def count_events() -> int:
    return len(_load(EVENTS_FILE))


def cleanup_old_events(keep_days: int = 30):
    """Удалить события старше keep_days дней."""
    events = _load(EVENTS_FILE)
    cutoff = date.today() - timedelta(days=keep_days)
    cleaned = {
        k: v for k, v in events.items()
        if _safe_date(v.get("event_date")) >= cutoff
    }
    removed = len(events) - len(cleaned)
    if removed:
        _save(EVENTS_FILE, cleaned)
        logger.info(f"Удалено устаревших событий: {removed}")
    return removed


def _safe_date(val) -> date:
    try:
        return date.fromisoformat(str(val))
    except Exception:
        return date.min


# ─── История публикаций ───────────────────────────────────────────────────────

def save_publication(
    msg_id: Optional[str],
    events_count: int,
    trigger: str = "scheduled",   # scheduled | manual
    success: bool = True,
    error: Optional[str] = None,
):
    """Записать факт публикации в историю."""
    history = _load(HISTORY_FILE)
    if not isinstance(history, list):
        history = []

    entry = {
        "published_at": datetime.utcnow().isoformat(),
        "telegram_msg_id": msg_id,
        "events_count": events_count,
        "trigger": trigger,
        "success": success,
        "error": error,
    }
    history.append(entry)

    # Оставляем последние 500 записей
    if len(history) > 500:
        history = history[-500:]

    _save(HISTORY_FILE, history)


def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Вернуть последние N публикаций."""
    history = _load(HISTORY_FILE)
    if not isinstance(history, list):
        return []
    return list(reversed(history[-limit:]))


# ─── Статистика ───────────────────────────────────────────────────────────────

def save_run_stats(stats: Dict[str, Any]):
    """Сохранить статистику последнего запуска сбора."""
    all_stats = _load(STATS_FILE)
    if not isinstance(all_stats, list):
        all_stats = []

    all_stats.append({
        "run_at": datetime.utcnow().isoformat(),
        **stats,
    })

    # Последние 100 запусков
    if len(all_stats) > 100:
        all_stats = all_stats[-100:]

    _save(STATS_FILE, all_stats)


def get_last_run_stats() -> Optional[Dict[str, Any]]:
    all_stats = _load(STATS_FILE)
    if isinstance(all_stats, list) and all_stats:
        return all_stats[-1]
    return None
