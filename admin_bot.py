"""
Telegram-бот для администраторов.

Команды:
  /start        — список команд
  /digest       — опубликовать дайджест прямо сейчас (7 дней)
  /collect      — запустить сбор данных
  /stats        — статистика последнего сбора
  /history      — история последних 10 публикаций
  /sources      — список источников
  /add          — добавить источник (диалог)
  /del          — удалить источник (диалог)
  /schedule     — просмотр/настройка расписания автозапуска
  /timezone     — выбор часового пояса
  /schedule_on  — включить автоматический режим
  /schedule_off — отключить автоматический режим
  /help         — справка

ADMIN_IDS в .env: через запятую, например: 123456789,987654321
"""
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ConversationHandler,
    MessageHandler, ContextTypes, filters,
)
from telegram.request import HTTPXRequest

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID  = os.getenv("TELEGRAM_CHANNEL_ID", "")
PROXY_URL   = os.getenv("PROXY_URL", "")
SOURCES_FILE = "sources.json"

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS   = set(
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
)

# ─── Состояния ConversationHandler ───────────────────────────────────────────
ADD_TYPE, ADD_NAME, ADD_URL = range(3)
DEL_PICK = range(1)

# Состояния для /schedule и /timezone
SCHED_WHAT, SCHED_TIME = range(10, 12)
TZ_PICK, TZ_CUSTOM = range(20, 22)


# ─── Построение Application ───────────────────────────────────────────────────

def _build_app() -> Application:
    builder = Application.builder().token(BOT_TOKEN)
    req_kwargs = dict(connect_timeout=30.0, read_timeout=30.0,
                      write_timeout=30.0, pool_timeout=30.0)
    if PROXY_URL:
        builder.request(HTTPXRequest(proxy=PROXY_URL, **req_kwargs))
    else:
        builder.request(HTTPXRequest(**req_kwargs))
    return builder.build()


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _load_sources() -> list:
    if not os.path.exists(SOURCES_FILE):
        return []
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_sources(sources: list):
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if ADMIN_IDS and uid not in ADMIN_IDS:
            await update.message.reply_text("⛔ Нет доступа.")
            return ConversationHandler.END
        return await func(update, ctx)
    return wrapper


# ─── Базовые команды ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Bali Events Admin*\n\n"
        "/digest — опубликовать дайджест\n"
        "/collect — запустить сбор\n"
        "/sources — список источников\n"
        "/add — добавить источник\n"
        "/del — удалить источник\n"
        "/stats — статистика сбора\n"
        "/history — история публикаций\n"
        "/schedule — расписание автозапуска\n"
        "/timezone — сменить часовой пояс\n"
        "/schedule\\_on — включить авторежим\n"
        "/schedule\\_off — выключить авторежим\n"
        "/help — справка",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_digest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Формирую дайджест за 7 дней...")
    try:
        from digest import compile_digest
        from bot import publish_digest as _publish
        import storage

        text = compile_digest(days=7)
        if not text:
            await update.message.reply_text("ℹ️ Нет событий за ближайшие 7 дней.")
            return

        msg_id = await _publish(text)
        if msg_id:
            events = storage.get_upcoming_events(days=7)
            storage.save_publication(msg_id, len(events), trigger="manual")
            await update.message.reply_text(
                f"✅ Опубликовано! ID: `{msg_id}`, событий: {len(events)}",
                parse_mode="Markdown",
            )
        else:
            storage.save_publication(None, 0, trigger="manual", success=False)
            await update.message.reply_text("❌ Ошибка публикации. Проверь лог.")
    except Exception as e:
        logger.error(f"cmd_digest: {e}", exc_info=True)
        await update.message.reply_text(f"❌ {e}")


@admin_only
async def cmd_collect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Запускаю сбор данных...")
    try:
        from collector import run_collection
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, run_collection)
        lines = [
            "✅ *Сбор завершён*\n",
            f"Сохранено: `{stats.get('saved', 0)}`",
            f"Дубликатов: `{stats.get('duplicates', 0)}`",
            f"Фильтр темы: `{stats.get('filtered_topic', 0)}`",
            f"Фильтр гео: `{stats.get('filtered_geo', 0)}`",
            f"Фильтр языка: `{stats.get('filtered_language', 0)}`\n",
            "*По источникам:*",
        ]
        for src, cnt in stats.get("sources", {}).items():
            lines.append(f"  • {src}: {cnt}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_collect: {e}", exc_info=True)
        await update.message.reply_text(f"❌ {e}")


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import storage
    stats = storage.get_last_run_stats()
    total = storage.count_events()
    if not stats:
        await update.message.reply_text(f"ℹ️ Нет данных. Событий в хранилище: {total}")
        return
    await update.message.reply_text(
        f"📊 *Последний сбор*\n\n"
        f"🕐 `{stats.get('run_at', '—')[:19]}`\n"
        f"✅ Сохранено: `{stats.get('saved', 0)}`\n"
        f"🔁 Дубликатов: `{stats.get('duplicates', 0)}`\n"
        f"🚫 Тема: `{stats.get('filtered_topic', 0)}`\n"
        f"🚫 Гео: `{stats.get('filtered_geo', 0)}`\n"
        f"🚫 Язык: `{stats.get('filtered_language', 0)}`\n\n"
        f"📦 Всего в хранилище: `{total}`",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import storage
    history = storage.get_history(limit=10)
    if not history:
        await update.message.reply_text("ℹ️ История пуста.")
        return
    lines = ["📋 *История публикаций*\n"]
    for h in history:
        ok      = "✅" if h.get("success") else "❌"
        trigger = "авто" if h.get("trigger") == "scheduled" else "ручной"
        dt      = h.get("published_at", "")[:16].replace("T", " ")
        lines.append(f"{ok} {dt} · {h.get('events_count','?')} событий · {trigger}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_sources(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sources = _load_sources()
    if not sources:
        await update.message.reply_text("ℹ️ Источники не настроены.")
        return
    lines = ["📡 *Источники*\n"]
    for i, s in enumerate(sources, 1):
        icon  = "✅" if s.get("enabled") else "⏸"
        stype = "TG" if s.get("type") == "telegram" else "WEB"
        ident = s.get("username") or s.get("url", "")
        lines.append(f"{i}. {icon} [{stype}] *{s['name']}*\n   `{ident}`")
    lines.append("\n/add — добавить  |  /del — удалить")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Справка*\n\n"
        "/digest — опубликовать дайджест прямо сейчас\n"
        "/collect — запустить сбор из всех источников\n"
        "/sources — список источников с номерами\n"
        "/add — добавить новый источник\n"
        "/del — удалить источник по номеру\n"
        "/stats — статистика последнего сбора\n"
        "/history — история 10 публикаций\n\n"
        "⏰ *Расписание:*\n"
        "/schedule — просмотр и настройка времени\n"
        "/timezone — выбор часового пояса\n"
        "/schedule\\_on — включить автосбор и автодайджест\n"
        "/schedule\\_off — выключить автосбор и автодайджест\n\n"
        "По умолчанию: сбор 08:00, дайджест 09:00 WITA.",
        parse_mode="Markdown",
    )


# ─── /schedule — просмотр и настройка расписания ─────────────────────────────

@admin_only
async def cmd_schedule_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Показать текущее расписание."""
    from scheduler_settings import get_schedule_display
    text = get_schedule_display()
    text += (
        "\n\n"
        "Изменить время: /schedule\n"
        "Сменить TZ: /timezone\n"
        "Вкл/откл: /schedule\\_on или /schedule\\_off"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def schedule_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Начало диалога /schedule — выбираем что менять."""
    from scheduler_settings import get_schedule_display
    text = get_schedule_display()
    keyboard = [
        ["📥 Время сбора данных"],
        ["📤 Время дайджеста"],
        ["❌ Отмена"],
    ]
    await update.message.reply_text(
        text + "\n\nЧто хочешь изменить?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return SCHED_WHAT


async def schedule_what(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Выбор — сбор или дайджест."""
    text = update.message.text.strip()
    if text.startswith("❌"):
        await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if "сбора" in text.lower() or "сбор" in text.lower():
        ctx.user_data["sched_field"] = "collect_time"
        label = "сбора данных"
    else:
        ctx.user_data["sched_field"] = "digest_time"
        label = "дайджеста"

    await update.message.reply_text(
        f"Введи новое время {label} в формате *ЧЧ:ММ*\n"
        f"Например: `08:30` или `21:00`\n\n"
        f"_Время задаётся в текущем часовом поясе_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SCHED_TIME


async def schedule_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Принять новое время."""
    from scheduler_settings import validate_time, update_setting, get_schedule_display

    time_str = update.message.text.strip()
    # Нормализуем: допускаем "9:00" → "09:00"
    parts = time_str.replace(".", ":").split(":")
    if len(parts) == 2:
        try:
            time_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            pass

    if not validate_time(time_str):
        await update.message.reply_text(
            "⚠️ Неверный формат. Введи время как `08:30` (часы:минуты, 24ч формат).",
            parse_mode="Markdown",
        )
        return SCHED_TIME

    field = ctx.user_data.get("sched_field", "digest_time")
    update_setting(field, time_str)

    label = "Сбор данных" if field == "collect_time" else "Дайджест"
    new_display = get_schedule_display()

    await update.message.reply_text(
        f"✅ *{label}* теперь запускается в `{time_str}`\n\n"
        f"{new_display}\n\n"
        f"_Планировщик обновится в течение минуты._",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def schedule_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ─── /timezone — смена часового пояса ────────────────────────────────────────

@admin_only
async def timezone_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Начало диалога выбора часового пояса."""
    from scheduler_settings import COMMON_TIMEZONES, load_settings

    current_tz = load_settings().get("timezone", "Asia/Makassar")

    keyboard = []
    for tz_id, tz_label in COMMON_TIMEZONES:
        mark = "✅ " if tz_id == current_tz else ""
        keyboard.append([f"{mark}{tz_label}"])
    keyboard.append(["✏️ Ввести вручную"])
    keyboard.append(["❌ Отмена"])

    await update.message.reply_text(
        f"🌍 *Текущий часовой пояс:* `{current_tz}`\n\n"
        "Выбери новый часовой пояс или введи вручную:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return TZ_PICK


async def timezone_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора часового пояса из списка."""
    from scheduler_settings import COMMON_TIMEZONES, validate_timezone, update_setting, get_schedule_display

    text = update.message.text.strip()

    if text.startswith("❌"):
        await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if "вручную" in text.lower() or "✏️" in text:
        await update.message.reply_text(
            "Введи название часового пояса в формате IANA:\n"
            "Например: `Europe/Moscow`, `Asia/Dubai`, `America/New_York`\n\n"
            "Полный список: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return TZ_CUSTOM

    # Ищем TZ ID по отображаемому имени
    clean = text.lstrip("✅").strip()
    found_tz = None
    for tz_id, tz_label in COMMON_TIMEZONES:
        if tz_label == clean or tz_label.lstrip("✅").strip() == clean:
            found_tz = tz_id
            break

    if not found_tz:
        await update.message.reply_text(
            "⚠️ Не удалось распознать выбор. Попробуй ещё раз или /timezone",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    return await _apply_timezone(update, found_tz)


async def timezone_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обработка ручного ввода часового пояса."""
    tz_str = update.message.text.strip()
    return await _apply_timezone(update, tz_str)


async def _apply_timezone(update: Update, tz_str: str):
    """Сохранить часовой пояс и уведомить."""
    from scheduler_settings import validate_timezone, update_setting, get_schedule_display

    if not validate_timezone(tz_str):
        await update.message.reply_text(
            f"⚠️ Неизвестный часовой пояс: `{tz_str}`\n\n"
            "Проверь название на https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    update_setting("timezone", tz_str)
    new_display = get_schedule_display()

    await update.message.reply_text(
        f"✅ Часовой пояс изменён на `{tz_str}`\n\n"
        f"{new_display}\n\n"
        f"_Планировщик обновится в течение минуты._",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ─── /schedule_on и /schedule_off ─────────────────────────────────────────────

@admin_only
async def cmd_schedule_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Включить и автосбор, и автодайджест."""
    from scheduler_settings import load_settings, save_settings, get_schedule_display
    s = load_settings()
    s["collect_enabled"] = True
    s["digest_enabled"] = True
    save_settings(s)
    display = get_schedule_display()
    await update.message.reply_text(
        f"✅ *Автоматический режим включён*\n\n{display}",
        parse_mode="Markdown",
    )


@admin_only
async def cmd_schedule_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Отключить автосбор и автодайджест."""
    from scheduler_settings import load_settings, save_settings
    s = load_settings()
    s["collect_enabled"] = False
    s["digest_enabled"] = False
    save_settings(s)
    await update.message.reply_text(
        "⏸ *Автоматический режим отключён*\n\n"
        "Сбор и дайджест теперь только вручную через /collect и /digest\n"
        "Включить обратно: /schedule\\_on",
        parse_mode="Markdown",
    )


# ─── /add — диалог добавления источника ──────────────────────────────────────

@admin_only
async def add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Telegram канал", "Сайт"]]
    await update.message.reply_text(
        "Выбери тип нового источника:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return ADD_TYPE


async def add_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "telegram" in text.lower() or "telegram" in text.lower():
        ctx.user_data["add_type"] = "telegram"
        ctx.user_data["add_hint"] = "username канала (без @), например: bali_invest"
    else:
        ctx.user_data["add_type"] = "website"
        ctx.user_data["add_hint"] = "полный URL сайта, например: https://example.com"

    await update.message.reply_text(
        "Введи название источника (любое, для удобства):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADD_NAME


async def add_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["add_name"] = update.message.text.strip()
    hint = ctx.user_data.get("add_hint", "")
    await update.message.reply_text(f"Введи {hint}:")
    return ADD_URL


async def add_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw      = update.message.text.strip()
    name     = ctx.user_data.get("add_name", "")
    src_type = ctx.user_data.get("add_type", "website")

    # Строим запись
    entry = {"name": name, "type": src_type, "enabled": True}
    if src_type == "telegram":
        entry["username"] = raw.lstrip("@")
    else:
        url = raw if raw.startswith("http") else f"https://{raw}"
        entry["url"] = url

    # Проверяем дубликат
    sources = _load_sources()
    for s in sources:
        if s.get("name") == name and s.get("type") == src_type:
            await update.message.reply_text(
                f"⚠️ Источник *{name}* уже существует.",
                parse_mode="Markdown",
            )
            return ConversationHandler.END

    sources.append(entry)
    _save_sources(sources)

    ident = entry.get("username") or entry.get("url", "")
    await update.message.reply_text(
        f"✅ Источник добавлен!\n\n"
        f"Название: *{name}*\n"
        f"Тип: {src_type}\n"
        f"Адрес: `{ident}`\n\n"
        f"Он будет использован при следующем /collect",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def add_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ─── /del — диалог удаления источника ────────────────────────────────────────

@admin_only
async def del_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sources = _load_sources()
    if not sources:
        await update.message.reply_text("ℹ️ Нет источников для удаления.")
        return ConversationHandler.END

    lines = ["Выбери номер источника для удаления:\n"]
    keyboard = []
    for i, s in enumerate(sources, 1):
        icon  = "✅" if s.get("enabled") else "⏸"
        stype = "TG" if s.get("type") == "telegram" else "WEB"
        ident = s.get("username") or s.get("url", "")
        lines.append(f"{i}. {icon} [{stype}] {s['name']} — `{ident}`")
        keyboard.append([f"{i}. {s['name']}"])

    keyboard.append(["❌ Отмена"])
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return DEL_PICK


async def del_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.startswith("❌"):
        await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    # Извлекаем номер из текста вида "3. Название"
    try:
        idx = int(text.split(".")[0]) - 1
    except (ValueError, IndexError):
        await update.message.reply_text(
            "⚠️ Не понял номер. Попробуй ещё раз или /del заново.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    sources = _load_sources()
    if idx < 0 or idx >= len(sources):
        await update.message.reply_text(
            "⚠️ Номер вне диапазона.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    removed = sources.pop(idx)
    _save_sources(sources)

    await update.message.reply_text(
        f"🗑 Источник удалён: *{removed['name']}*\n"
        f"Осталось источников: {len(sources)}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ─── Запуск ───────────────────────────────────────────────────────────────────

def run_admin_bot():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не задан")
        return

    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS не задан — бот доступен всем!")

    app = _build_app()

    # Простые команды
    app.add_handler(CommandHandler("start",        cmd_start))
    app.add_handler(CommandHandler("digest",       cmd_digest))
    app.add_handler(CommandHandler("collect",      cmd_collect))
    app.add_handler(CommandHandler("stats",        cmd_stats))
    app.add_handler(CommandHandler("history",      cmd_history))
    app.add_handler(CommandHandler("sources",      cmd_sources))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("schedule_on",  cmd_schedule_on))
    app.add_handler(CommandHandler("schedule_off", cmd_schedule_off))

    # /schedule_view — просмотр без диалога (через аргументы команды schedule)
    # При вызове /schedule без диалога — показываем текущее расписание
    # (диалог /schedule обрабатывается ConversationHandler ниже)

    # Диалог /add
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_type)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_URL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_url)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        name="add_source",
    ))

    # Диалог /del
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("del", del_start)],
        states={
            DEL_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_pick)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        name="del_source",
    ))

    # Диалог /schedule — настройка времени
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("schedule", schedule_start)],
        states={
            SCHED_WHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_what)],
            SCHED_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_time)],
        },
        fallbacks=[CommandHandler("cancel", schedule_cancel)],
        name="schedule_dialog",
    ))

    # Диалог /timezone — выбор часового пояса
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("timezone", timezone_start)],
        states={
            TZ_PICK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, timezone_pick)],
            TZ_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, timezone_custom)],
        },
        fallbacks=[CommandHandler("cancel", schedule_cancel)],
        name="timezone_dialog",
    ))

    logger.info(f"Admin bot запущен. Админы: {ADMIN_IDS or 'все'}")
    app.run_polling(drop_pending_updates=True)
