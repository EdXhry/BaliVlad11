"""
Фильтры по ТЗ — смысловая проверка темы.

Логика:
  Пост релевантен ТОЛЬКО если одновременно:
  1. Тема = недвижимость/инвестиции в бетон/землю (не туризм, не IT, не спорт)
  2. Формат = событие (конференция/форум/встреча/выставка/вебинар)
  3. Не попал в явные исключения (юр/миграция/мастер-классы)

Широкие слова типа "rent", "land", "development", "investment", "property"
допускаются ТОЛЬКО в устойчивых словосочетаниях с недвижимостью,
иначе они триггерят туризм, IT, сельское хозяйство и т.д.
"""
import re
from typing import Optional, Tuple


# ─── ОДНОЗНАЧНЫЕ слова темы (всегда про недвижимость) ────────────────────────
STRONG_TOPIC_KEYWORDS = {
    # RU
    "инвестиц",            # инвестиции, инвестирование — достаточно сильный сигнал
    "недвижимост",         # недвижимость, недвижимости
    "девелопмент",
    "девелопер",
    "вилла", "виллу",
    "страта",
    "рои",
    "апартамент",
    "управлени недвижим",
    "арендный бизнес",
    "налог на недвижим",
    "налогообложени недвижим",
    "земельн участ",       # земельный участок — конкретно
    # EN — только устойчивые составные
    "real estate",
    "property investment",
    "property management",
    "property development",
    "commercial property",
    "residential property",
    "property tax",
    "rental yield",        # доходность аренды — конкретно
    "rental income",
    "villa investment",
    "land acquisition",
    "coliving",
    "strata",
    "leasehold",
    "freehold",
    "roi",                 # в контексте инвест-ивентов
    "yield",               # доходность — принимаем в связке с event-маркером
}

# ─── КОНТЕКСТНЫЕ слова (принимаем только если рядом есть сильный сигнал) ─────
# Сами по себе слишком широкие — "property" может быть про IT, "villa" про туризм
WEAK_TOPIC_KEYWORDS = {
    "property",    # слишком широкое: "property rights", "intellectual property"
    "villa",       # может быть просто аренда жилья для туристов
    "investment",  # "investment in education", "investment in health"
    "development", # "software development", "personal development"
    "rent",        # "rent a car", "rent a bike"
    "land",        # "land tour", "land transfer"
    "налог",       # "налог на доход", "налог на авто"
}

# ─── ИСКЛЮЧЕНИЯ — если есть, сразу отклоняем ─────────────────────────────────
HARD_EXCLUDE = {
    # юр/миграция — по ТЗ явно
    "юрист", "юридическ", "юриспруд", "адвокат",
    "миграц", "внж", "вид на жительство",
    "резидентств", "immigration", "residency",
    # мастер-классы — по ТЗ явно
    "мастер-класс", "masterclass",
    "курс обучени",
    # простые объявления без события
    "сдаю", "сдам", "продаю", "продам",
    "property for sale", "property for rent",
    "available for rent", "available for sale",
    "apartments for rent", "villas for rent",
    # zoom-only
    "zoom-only", "online-only",
}

# ─── НЕРЕЛЕВАНТНЫЕ ТЕМЫ — даже если есть слово "инвестиции" ─────────────────
EXCLUDE_TOPICS = {
    # туризм (главный враг — Бали туристический)
    "тур ", "туристич", "экскурси", "трансфер", "tour ", "tourism", "excursion",
    # спорт
    "футбол", "football", "soccer", "спортивн", "хоккей", "баскетбол",
    "теннис", "гольф", "серфинг", "йога", "фитнес", "surf",
    # здоровье / медицина
    "медицин", "wellness", "терапи", "massage", "массаж",
    "косметолог", "beauty", "spa", "детокс", "detox", "health clinic",
    # еда / вечеринки
    "ресторан", "restaurant", "кофе", "coffee", "кулинар",
    "барбекю", "вечеринка", "party", "концерт", "concert", "dj ",
    # IT / tech (не связанные с proptech)
    "telecom", "телеком", "5g", "blockchain", "crypto", "cryptocurrency",
    "software", "cybersecurity", "programming", "python", "javascript",
    # энергетика / добыча
    "energy sector", "oil ", "gas sector", "mining sector", "нефтян", "добыч нефт",
    # сельское хозяйство
    "agriculture", "farming", "agri",
    # мода / искусство
    "fashion", "мода", "фотовыставк", "photo exhibition",
    "музыка", "music", "танц", "dance",
    # образование общее
    "university admissions", "school enrollment",
}

# ─── Маркеры типа события (с границами слов) ─────────────────────────────────
EVENT_MARKER_PATTERNS = [
    r'\bконференци',           # конференция, конференции
    r'\bconference\b',
    r'\bфорум\b',              # только отдельное слово
    r'\bforum\b',
    r'\bвстреча\b',
    r'\bmeetup\b',
    r'\bmeet[\s\-]?up\b',
    r'\bmeeting\b',
    r'\bвыставка\b',
    r'\bexhibition\b',
    r'\bexpo\b',
    r'\bсеминар\b',
    r'\bseminar\b',
    r'\bнетворкинг\b',
    r'\bnetworking\b',
    r'\bвебинар\b',
    r'\bwebinar\b',
    r'\bмитап\b',
    r'\bпитч[\s\-]?сессия',
    r'\bpitch[\s\-]?session',
    r'\bсаммит\b',
    r'\bsummit\b',
    r'\bпрезентаци',           # презентация, презентации
    r'\bpresentation\b',
    r'\bкруглый стол\b',
    r'\broundtable\b',
]

# ─── Районы Бали ─────────────────────────────────────────────────────────────
BALI_DISTRICTS = {
    "bali", "бали",
    "denpasar", "денпасар",
    "canggu", "чангу",
    "ubud", "убуд",
    "seminyak", "семиньяк",
    "sanur", "санур",
    "kuta", "кута",
    "jimbaran", "джимбаран",
    "uluwatu", "улувату",
    "nusa dua", "нуса дуа",
    "bukit", "букит",
}

# ─── Типы мероприятий ────────────────────────────────────────────────────────
EVENT_TYPE_MAP = {
    "форум":      "forum",
    "forum":      "forum",
    "конференц":  "conference",
    "conference": "conference",
    "встреча":    "meetup",
    "митап":      "meetup",
    "meetup":     "meetup",
    "meet up":    "meetup",
    "выставка":   "exhibition",
    "exhibition": "exhibition",
    "expo":       "exhibition",
    "семинар":    "seminar",
    "seminar":    "seminar",
    "вебинар":    "seminar",
    "webinar":    "seminar",
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


# ─── Основная функция проверки темы ──────────────────────────────────────────

def is_relevant_topic(text: str) -> bool:
    """
    Смысловая проверка: пост про инвестиции в недвижимость/бетон/землю?

    Шаги:
    1. Нерелевантные темы (туризм, спорт, IT...) → сразу False
    2. Жёсткие исключения (юрист, миграция, объявления) → False
    3. Сильный сигнал темы (real estate, девелопмент...) → has_strong_topic
    4. Слабый сигнал темы (property, villa...) → has_weak_topic
    5. Маркер события (конференция, форум...) → has_event
    6. Итог: (сильный OR слабый) AND событие → True
       Слабый сигнал без сильного — только если маркер события очень конкретный
    """
    t = text.lower()

    # 1. Нерелевантные темы — туризм главный враг на Бали
    for kw in EXCLUDE_TOPICS:
        if kw in t:
            return False

    # 2. Жёсткие исключения
    for kw in HARD_EXCLUDE:
        if kw in t:
            return False

    # 3 & 4. Проверяем тему
    has_strong = any(kw in t for kw in STRONG_TOPIC_KEYWORDS)
    has_weak   = any(kw in t for kw in WEAK_TOPIC_KEYWORDS)
    has_topic  = has_strong or has_weak

    if not has_topic:
        return False

    # 5. Маркер типа события
    has_event = any(re.search(p, t) for p in EVENT_MARKER_PATTERNS)

    if not has_event:
        return False

    # 6. Слабый сигнал без сильного — требуем оба маркера подтверждения
    #    Например "villa" + "forum" без "real estate" — может быть туризм
    #    Поэтому при слабом сигнале проверяем что тема более конкретная
    if has_weak and not has_strong:
        # Слабый сигнал принимаем только если есть хотя бы 2 слова из темы
        # или есть слово контекста недвижимости в описании
        property_context = [
            "недвижим", "real estate", "invest", "инвест",
            "девелоп", "стратег", "доходност", "yield", "roi",
        ]
        context_count = sum(1 for w in property_context if w in t)
        if context_count < 1:
            return False

    return True


def is_bali_location(text: str) -> bool:
    """Явно упоминается Бали или один из его районов."""
    t = text.lower()
    return any(d in t for d in BALI_DISTRICTS)


def is_online(text: str) -> bool:
    """Мероприятие проходит онлайн."""
    t = text.lower()
    return any(w in t for w in [
        "online", "онлайн", "webinar", "вебинар",
        "zoom", "stream", "стрим", "трансляция",
        "virtual", "виртуальн", "youtube live",
    ])


def detect_language(text: str) -> str:
    """Определить язык по наличию кириллицы/латиницы."""
    has_ru = bool(re.search(r"[а-яА-ЯёЁ]", text))
    has_en = bool(re.search(r"[a-zA-Z]{3,}", text))
    if has_ru and has_en:
        return "ru+en"
    if has_ru:
        return "ru"
    if has_en:
        return "en"
    return "unknown"


def extract_event_type(text: str) -> str:
    """Определить тип мероприятия, вернуть EN-код."""
    t = text.lower()
    for keyword, etype in EVENT_TYPE_MAP.items():
        if keyword in t:
            return etype
    return "event"


def extract_speakers(text: str) -> Optional[str]:
    """Извлечь имена спикеров."""
    patterns = [
        r"(?:спикер[ы]?[:：]?)\s*([^\n.]{3,80})",
        r"(?:speaker[s]?[:：]?)\s*([^\n.]{3,80})",
        r"(?:ведущий[:：]?)\s*([^\n.]{3,80})",
        r"(?:presenter[:：]?)\s*([^\n.]{3,80})",
        r"(?:модератор[:：]?)\s*([^\n.]{3,80})",
        r"(?:докладчик[:：]?)\s*([^\n.]{3,80})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:100]
    return None


# ─── Обратная совместимость ───────────────────────────────────────────────────
def is_relevant_topic_legacy(text: str) -> bool:
    return is_relevant_topic(text)

def is_bali_location_legacy(text: str) -> bool:
    return is_bali_location(text)

def is_online_only(text: str) -> bool:
    return is_online(text)

def extract_event_type_tuple(text: str) -> Tuple[str, str]:
    en = extract_event_type(text)
    return EVENT_TYPE_RU.get(en, "мероприятие"), en

INCLUDE_KEYWORDS     = STRONG_TOPIC_KEYWORDS
EXCLUDE_KEYWORDS     = HARD_EXCLUDE
INCLUDE_KEYWORDS_RU  = STRONG_TOPIC_KEYWORDS
INCLUDE_KEYWORDS_EN  = STRONG_TOPIC_KEYWORDS
EXCLUDE_KEYWORDS_RU  = HARD_EXCLUDE
EXCLUDE_KEYWORDS_EN  = HARD_EXCLUDE
