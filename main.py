"""
Точка входа. Запускает планировщик + admin Telegram-бот одновременно.

Использование:
  python main.py            — планировщик + admin-бот (основной режим)
  python main.py collect    — ручной сбор прямо сейчас
  python main.py publish    — ручная публикация прямо сейчас
  python main.py test-bot   — проверить подключение к Telegram

Требования: только .env с токенами. PostgreSQL НЕ нужен.
"""
import asyncio
import logging
import sys
import threading
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── Логирование ──────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─── Планировщик ──────────────────────────────────────────────────────────────

def job_collect():
    logger.info("=" * 50)
    logger.info("ЗАДАЧА: сбор данных")
    try:
        from collector import run_collection
        stats = run_collection()
        logger.info(f"Сбор OK: сохранено={stats['saved']}, дубл={stats['duplicates']}")
    except Exception as e:
        logger.error(f"Ошибка сбора: {e}", exc_info=True)


def job_publish():
    logger.info("=" * 50)
    logger.info("ЗАДАЧА: публикация дайджеста")
    try:
        from digest import compile_digest
        from bot import publish_digest
        import storage

        text = compile_digest(days=7)
        if not text:
            logger.info("Нет событий для публикации")
            return

        msg_id = asyncio.run(publish_digest(text))
        events_count = len(storage.get_recently_added_events(days=7))
        storage.save_publication(msg_id, events_count, trigger="scheduled", success=bool(msg_id))

        if msg_id:
            logger.info(f"Опубликовано, msg_id={msg_id}")
        else:
            logger.error("Публикация не удалась")

        # Чистим устаревшие события
        storage.cleanup_old_events(keep_days=30)

    except Exception as e:
        logger.error(f"Ошибка публикации: {e}", exc_info=True)
        try:
            import storage as _s
            _s.save_publication(None, 0, trigger="scheduled", success=False, error=str(e))
        except Exception:
            pass


def run_scheduler():
    """
    Запустить планировщик в отдельном потоке.
    Расписание читается из data/settings.json и обновляется динамически
    при каждом срабатывании задачи check_schedule_update.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from scheduler_settings import load_settings, time_to_utc

    scheduler = BlockingScheduler(timezone="UTC")
    
    # Кеш последних настроек для избежания пересоздания задач
    _last_schedule = {
        "collect_time": None,
        "collect_enabled": None,
        "digest_time": None,
        "digest_enabled": None,
        "timezone": None,
    }

    def _reload_jobs():
        """Перечитать настройки и обновить задачи планировщика ТОЛЬКО если изменились."""
        try:
            s = load_settings()
            tz = s.get("timezone", "UTC")
            collect_local = s.get("collect_time", "08:00")
            collect_enabled = s.get("collect_enabled", True)
            digest_local = s.get("digest_time", "09:00")
            digest_enabled = s.get("digest_enabled", True)

            # Проверяем изменились ли настройки
            if (_last_schedule["collect_time"] == collect_local and
                _last_schedule["collect_enabled"] == collect_enabled and
                _last_schedule["digest_time"] == digest_local and
                _last_schedule["digest_enabled"] == digest_enabled and
                _last_schedule["timezone"] == tz):
                # Настройки не изменились, ничего не делаем
                return

            # Настройки изменились, обновляем задачи
            logger.info(f"Обновление расписания: timezone={tz}, collect={collect_local}, digest={digest_local}")

            # Вычисляем UTC время для collect
            collect_utc = time_to_utc(collect_local, tz)
            if collect_utc:
                ch, cm = map(int, collect_utc.split(":"))
            else:
                ch, cm = 0, 0

            # Вычисляем UTC время для digest
            digest_utc = time_to_utc(digest_local, tz)
            if digest_utc:
                dh, dm = map(int, digest_utc.split(":"))
            else:
                dh, dm = 1, 0

            # Обновляем задачи (replace_existing=True)
            if collect_enabled:
                scheduler.add_job(
                    job_collect,
                    CronTrigger(hour=ch, minute=cm, timezone="UTC"),
                    id="collect", replace_existing=True,
                )
                logger.info(f"Планировщик: сбор {collect_local} {tz} → {collect_utc} UTC (каждый день)")
            else:
                # Удаляем задачу если отключена
                try:
                    scheduler.remove_job("collect")
                    logger.info("Планировщик: сбор отключён")
                except Exception:
                    pass

            if digest_enabled:
                scheduler.add_job(
                    job_publish,
                    CronTrigger(hour=dh, minute=dm, timezone="UTC"),
                    id="publish", replace_existing=True,
                )
                logger.info(f"Планировщик: дайджест {digest_local} {tz} → {digest_utc} UTC (каждый день)")
            else:
                try:
                    scheduler.remove_job("publish")
                    logger.info("Планировщик: дайджест отключён")
                except Exception:
                    pass

            # Сохраняем текущие настройки в кеш
            _last_schedule["collect_time"] = collect_local
            _last_schedule["collect_enabled"] = collect_enabled
            _last_schedule["digest_time"] = digest_local
            _last_schedule["digest_enabled"] = digest_enabled
            _last_schedule["timezone"] = tz

        except Exception as e:
            logger.error(f"Ошибка обновления расписания: {e}", exc_info=True)

    # Задача проверки изменений настроек — каждую минуту
    scheduler.add_job(
        _reload_jobs,
        CronTrigger(minute="*"),
        id="check_settings",
        replace_existing=True,
    )

    # Первоначальная загрузка расписания
    _reload_jobs()

    logger.info("Планировщик запущен (динамическое расписание из data/settings.json)")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Планировщик остановлен")


# Глобальная ссылка на планировщик для перезагрузки из admin-бота
_scheduler_reload_flag = {"reload": False}


def request_scheduler_reload():
    """Пометить флаг перезагрузки расписания (вызывается из admin_bot)."""
    _scheduler_reload_flag["reload"] = True


# ─── CLI команды ──────────────────────────────────────────────────────────────

def cmd_collect():
    print("=" * 50)
    print("РУЧНОЙ СБОР")
    job_collect()


def cmd_publish():
    print("=" * 50)
    print("РУЧНАЯ ПУБЛИКАЦИЯ")
    job_publish()


def cmd_test_bot():
    print("=" * 50)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К TELEGRAM")

    async def _test():
        from bot import test_connection, send_test_message
        ok = await test_connection()
        if ok:
            channel = os.getenv("TELEGRAM_CHANNEL_ID")
            print(f"Отправляю тест в {channel}...")
            await send_test_message()
        else:
            print("Не удалось подключиться")

    asyncio.run(_test())


# ─── Главная точка входа ──────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        # Основной режим: планировщик + admin-бот одновременно
        logger.info("Запуск: планировщик + admin-бот")

        # Admin-бот в отдельном daemon-потоке с автоперезапуском
        def _run_admin():
            import asyncio, time
            while True:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    from admin_bot import run_admin_bot
                    run_admin_bot()
                except Exception as e:
                    logger.error(f"Admin-бот упал: {e}", exc_info=True)
                finally:
                    loop.close()
                logger.info("Admin-бот перезапустится через 30 сек...")
                time.sleep(30)

        t = threading.Thread(target=_run_admin, daemon=True, name="admin-bot")
        t.start()

        # Планировщик в главном потоке (блокирует до Ctrl+C)
        run_scheduler()
        return

    command = sys.argv[1]
    commands = {
        "collect":  cmd_collect,
        "publish":  cmd_publish,
        "test-bot": cmd_test_bot,
    }
    if command in commands:
        commands[command]()
    else:
        print("Команды: collect | publish | test-bot")
        print("Без аргументов — основной режим (планировщик + admin-бот)")


if __name__ == "__main__":
    main()
