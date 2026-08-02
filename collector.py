"""
Оркестратор сбора данных. Не требует БД — работает с JSON-хранилищем.
"""
import json
import logging
import os
import yaml
from typing import Any, Dict, List, Optional

from parsers.universal_parser import UniversalParser
from processor import process_events
import storage

logger = logging.getLogger(__name__)

SOURCES_FILE = "sources.json"
CONFIG_FILE  = "source_configs.yaml"


def load_sources_from_file() -> List[Dict[str, Any]]:
    if not os.path.exists(SOURCES_FILE):
        logger.warning(f"{SOURCES_FILE} не найден")
        return []
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [s for s in data if s.get("enabled", False)]
    except Exception as e:
        logger.error(f"Ошибка загрузки {SOURCES_FILE}: {e}")
        return []


def get_active_sources() -> List[Dict[str, Any]]:
    return load_sources_from_file()


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Ошибка загрузки {CONFIG_FILE}: {e}")
    return {
        "telegram": {"default_location": "Bali, Indonesia"},
        "default_website": {
            "parsing_rules": {
                "event_selector":       "article, .post, .card, .item, .entry, .event",
                "title_selector":       "h1, h2, h3, h4, .title, [class*='title']",
                "date_selector":        "time, .date, [class*='date'], [datetime]",
                "location_selector":    ".location, .place, .venue, [class*='location']",
                "description_selector": ".excerpt, .summary, p, [class*='desc']",
                "price_selector":       ".price, .cost, [class*='price']",
                "link_selector":        "a[href]",
                "default_location":     "Bali, Indonesia",
            }
        },
    }


def create_parser_for_source(
    source_config: Dict[str, Any],
    config: Dict[str, Any],
) -> Optional[UniversalParser]:
    name        = source_config.get("name", "Unknown")
    source_type = source_config.get("type", "website")
    try:
        if source_type == "telegram":
            username = source_config.get("username", "").lstrip("@")
            if not username:
                logger.error(f"'{name}': нет username")
                return None
            rules = {"default_location": config.get("telegram", {}).get("default_location", "Bali, Indonesia")}
            return UniversalParser(name, username, rules, "telegram")
        else:
            url = source_config.get("url", "")
            if not url:
                logger.error(f"'{name}': нет url")
                return None
            rules = dict(config.get("default_website", {}).get("parsing_rules", {}))
            for site_cfg in config.get("sources", {}).values():
                if isinstance(site_cfg, dict):
                    if site_cfg.get("url", "").rstrip("/") == url.rstrip("/") or \
                       site_cfg.get("name", "").lower() == name.lower():
                        rules.update(site_cfg.get("parsing_rules", {}))
                        break
            return UniversalParser(name, url, rules, "website")
    except Exception as e:
        logger.error(f"Ошибка парсера '{name}': {e}")
        return None


def add_source(source_type: str, name: str, url_or_username: str = None) -> bool:
    try:
        sources = []
        if os.path.exists(SOURCES_FILE):
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                sources = json.load(f)
        for s in sources:
            if s.get("name") == name and s.get("type") == source_type:
                return False
        entry: Dict[str, Any] = {"name": name, "type": source_type, "enabled": True}
        if url_or_username:
            if source_type == "telegram":
                entry["username"] = url_or_username.lstrip("@")
            else:
                entry["url"] = url_or_username
        sources.append(entry)
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        logger.info(f"Источник '{name}' добавлен")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления источника: {e}")
        return False


def run_collection() -> dict:
    """
    Сбор со всех активных источников. Не требует БД.
    """
    all_raw    = []
    per_source = {}
    config     = load_config()
    sources    = get_active_sources()

    logger.info(f"Сбор: {len(sources)} источников")

    for src in sources:
        name = src.get("name", "?")
        geo  = src.get("geo", "bali")  # bali или world
        try:
            logger.info(f"  → {name} [{geo}]")
            parser = create_parser_for_source(src, config)
            if not parser:
                per_source[name] = 0
                continue
            raw = parser.parse()
            # Проставляем geo из конфига источника в каждое сырое событие
            for event in raw:
                if hasattr(event, "__dict__"):
                    event.__dict__["source_geo"] = geo
                elif isinstance(event, dict):
                    event["source_geo"] = geo
            per_source[name] = len(raw)
            all_raw.extend(raw)
            logger.info(f"     {len(raw)} сообщений")
            if hasattr(parser, "close"):
                parser.close()
        except Exception as e:
            per_source[name] = 0
            logger.error(f"  ✗ {name}: {e}", exc_info=True)

    logger.info(f"Всего сырых: {len(all_raw)}")
    save_stats = process_events(all_raw)
    result = {"sources": per_source, "total_raw": len(all_raw), **save_stats}
    storage.save_run_stats(result)
    return result
