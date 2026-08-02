"""
Хранение и управление настройками планировщика.

Настройки сохраняются в data/settings.json:
  - timezone: часовой пояс (например, "Asia/Makassar" = WITA)
  - collect_time: время сбора данных "HH:MM"
  - digest_time: время публикации дайджеста "HH:MM"
  - collect_enabled: включён ли автосбор
  - digest_enabled: включён ли автодайджест
"""
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# Значения по умолчанию
DEFAULT_SETTINGS: Dict[str, Any] = {
    "timezone": "UTC+3",           # МСК (UTC+3) - Москва
    "collect_time": "04:40",        # за 20 минут до дайджеста
    "digest_time": "05:00",         # 05:00 МСК = 09:00 WITA (Бали)
    "collect_enabled": True,
    "digest_enabled": True,
}

# Популярные часовые пояса для меню
COMMON_TIMEZONES = [
    ("UTC+3",           "МСК UTC+3 (Москва)"),
    ("UTC+8",           "WITA UTC+8 (Бали)"),
    ("UTC+0",           "GMT UTC+0 (Лондон)"),
    ("UTC-5",           "EST UTC-5 (Нью-Йорк)"),
]


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_settings() -> Dict[str, Any]:
    """Загрузить настройки, применив дефолты для отсутствующих полей."""
    _ensure_dir()
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
    return settings


def save_settings(settings: Dict[str, Any]) -> bool:
    """Сохранить настройки."""
    _ensure_dir()
    try:
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_FILE)
        logger.info(f"Настройки сохранены: {settings}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False


def update_setting(key: str, value: Any) -> bool:
    """Обновить одно поле настроек."""
    settings = load_settings()
    settings[key] = value
    return save_settings(settings)


def get_setting(key: str, default: Any = None) -> Any:
    """Получить одно поле настроек."""
    return load_settings().get(key, default)


def validate_time(time_str: str) -> bool:
    """Проверить формат времени HH:MM."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return False
        h, m = int(parts[0]), int(parts[1])
        return 0 <= h <= 23 and 0 <= m <= 59
    except (ValueError, AttributeError):
        return False


def validate_timezone(tz_str: str) -> bool:
    """Проверить корректность часового пояса."""
    try:
        import zoneinfo
        zoneinfo.ZoneInfo(tz_str)
        return True
    except Exception:
        try:
            import pytz
            pytz.timezone(tz_str)
            return True
        except Exception:
            return False


def time_to_utc(local_time: str, timezone: str) -> Optional[str]:
    """
    Конвертировать локальное время в UTC.
    Возвращает строку "HH:MM" в UTC или None при ошибке.
    
    Поддерживает как полные имена timezone (Europe/Moscow), так и упрощённые офсеты (UTC+3).
    """
    try:
        from datetime import datetime, timedelta
        import datetime as dt_module
        h, m = map(int, local_time.split(":"))

        # Если timezone в формате UTC+X или UTC-X, используем простую арифметику
        if timezone.upper().startswith("UTC"):
            offset_str = timezone[3:].strip()  # +8, -5, etc
            if offset_str:
                offset_hours = int(offset_str)
                utc_hour = (h - offset_hours) % 24
                return f"{utc_hour:02d}:{m:02d}"
            else:
                # Просто UTC
                return f"{h:02d}:{m:02d}"

        # Пробуем использовать timezone database
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
        except Exception:
            try:
                import pytz
                tz = pytz.timezone(timezone)
            except Exception:
                # Фоллбэк: пробуем парсить как офсет
                logger.warning(f"Timezone '{timezone}' не найден, попытка использовать UTC")
                return f"{h:02d}:{m:02d}"

        # Создаём datetime на сегодня в нужном TZ
        now = datetime.now(tz=tz)
        local_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

        # Конвертируем в UTC
        utc_dt = local_dt.astimezone(dt_module.timezone.utc)
        return utc_dt.strftime("%H:%M")
    except Exception as e:
        logger.error(f"Ошибка конвертации времени: {e}")
        return None


def get_schedule_display() -> str:
    """Вернуть читаемое описание текущего расписания."""
    s = load_settings()
    tz = s["timezone"]
    collect_utc = time_to_utc(s["collect_time"], tz) or "?"
    digest_utc = time_to_utc(s["digest_time"], tz) or "?"

    # Найдём отображаемое имя TZ
    tz_display = tz
    for tz_id, tz_label in COMMON_TIMEZONES:
        if tz_id == tz:
            tz_display = tz_label
            break

    lines = [
        f"⏰ *Настройки расписания*\n",
        f"🌍 Часовой пояс: `{tz_display}`",
        f"📥 Сбор данных: `{s['collect_time']}` {'✅' if s['collect_enabled'] else '⏸'}"
        f" (UTC: `{collect_utc}`)",
        f"📤 Дайджест:    `{s['digest_time']}` {'✅' if s['digest_enabled'] else '⏸'}"
        f" (UTC: `{digest_utc}`)",
    ]
    return "\n".join(lines)
