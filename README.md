# Bali Real Estate Events Bot

Telegram-бот, который ежедневно собирает анонсы мероприятий по инвестициям и недвижимости на Бали и публикует дайджест в закрытый канал.

**Что собирает:**
- Оффлайн-события на Бали (RU + EN): форумы, конференции, митапы, выставки
- Онлайн-события по всему миру — только на русском языке, по той же теме

**Что фильтрует:** вебинары/стримы без темы, юрист/миграция/ВНЖ, мастер-классы, оффлайн вне Бали

---

## Структура проекта

```
bot_bali/
│
├── main.py                  # Точка входа. Запускает планировщик + admin-бот
├── admin_bot.py             # Telegram admin-бот (команды /add, /del, /digest и др.)
├── bot.py                   # Публикация дайджеста в канал
├── collector.py             # Оркестратор сбора: читает sources.json, запускает парсеры
├── processor.py             # Фильтрация событий по ТЗ, сохранение в хранилище
├── digest.py                # Формирование текста дайджеста
├── storage.py               # JSON-хранилище (замена БД)
├── config.py                # Ключевые слова включения/исключения, фильтры
│
├── sources.json             # Список источников (Telegram-каналы и сайты)
├── source_configs.yaml      # Правила парсинга для конкретных сайтов
│
├── parsers/
│   ├── base.py              # Базовый класс парсера (HTTP, retry, User-Agent)
│   ├── universal_parser.py  # Универсальный парсер для сайтов и TG
│   └── telegram_parser.py   # Парсер Telegram через MTProto API (Telethon)
│
├── init_telegram_session.py # Одноразовая авторизация Telethon-сессии
├── telegram_session.session # Файл сессии Telethon (создаётся при авторизации)
│
├── data/                    # JSON-хранилище данных (создаётся автоматически)
│   ├── events.json          # Собранные события
│   ├── history.json         # История публикаций
│   └── stats.json           # Статистика запусков
│
├── logs/
│   └── bot.log              # Лог работы бота
│
├── tests/                   # Тестовые скрипты (не нужны для работы)
├── .env                     # Настройки (токены, ID, расписание)
├── requirements.txt         # Зависимости Python
└── .gitignore
```

---

## Быстрый старт

### 1. Клонировать и установить зависимости

```bash
git clone <репозиторий>
cd bot_bali
python -m venv venv

# Windows
venv\Scripts\pip.exe install -r requirements.txt

# Linux / macOS
venv/bin/pip install -r requirements.txt
```

### 2. Настроить .env

Скопируй `.env` и заполни:

```env
# Токен бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN=ваш_токен

# ID канала куда публиковать дайджест
# Для публичного: @channel_name
# Для приватного: -1001234567890
TELEGRAM_CHANNEL_ID=@your_channel

# Администраторы бота — Telegram user_id через запятую
# Узнать свой ID: написать @userinfobot
ADMIN_IDS=123456789,987654321

# MTProto API для парсинга Telegram-каналов
# Получить на https://my.telegram.org → App configuration
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE=+7xxxxxxxxxx

# Прокси (только если запускаешь из России, где Telegram заблокирован)
# PROXY_URL=http://user:password@ip:port

# Расписание (UTC, формат cron)
# 09:00 WITA = 01:00 UTC
COLLECTION_SCHEDULE=0 0 * * *
PUBLICATION_SCHEDULE=0 1 * * *
```

### 3. Авторизовать Telethon-сессию (один раз)

```bash
# Windows
venv\Scripts\python.exe init_telegram_session.py

# Linux / macOS
venv/bin/python init_telegram_session.py
```

Введи код из Telegram. Создастся файл `telegram_session.session` — он хранит авторизацию, повторный вход не нужен.

### 4. Добавить бота в канал

Открой канал → Управление → Администраторы → добавь своего бота с правом отправки сообщений.

### 5. Запустить

```bash
# Windows
venv\Scripts\python.exe main.py

# Linux / macOS
venv/bin/python main.py
```

Бот запустится в двух режимах одновременно:
- **Планировщик** — автоматический сбор и публикация по расписанию
- **Admin-бот** — принимает команды от администраторов

---

## Управление источниками

Источники хранятся в `sources.json`. Управлять можно двумя способами:

### Через admin-бота в Telegram

- `/sources` — посмотреть список
- `/add` — добавить источник (диалог: тип → название → адрес)
- `/del` — удалить источник (выбор из списка кнопками)

### Вручную в sources.json

```json
[
  {
    "name": "Bali Invest",
    "type": "telegram",
    "username": "bali_invest",
    "enabled": true
  },
  {
    "name": "PP Bali",
    "type": "website",
    "url": "https://ppbali.com/",
    "enabled": true
  }
]
```

**Поля:**
- `type` — `telegram` или `website`
- `username` — для Telegram: имя канала без `@` (канал должен быть публичным)
- `url` — для сайтов: полный URL
- `enabled` — `true` / `false` (выключить источник без удаления)

Изменения подхватываются при следующем сборе — перезапуск не нужен.

---

## Команды admin-бота

| Команда | Что делает |
|---------|------------|
| `/digest` | Собрать и опубликовать дайджест прямо сейчас (события за 7 дней) |
| `/collect` | Запустить сбор данных из всех источников |
| `/sources` | Список источников с номерами |
| `/add` | Добавить источник (пошаговый диалог) |
| `/del` | Удалить источник (выбор из списка) |
| `/stats` | Статистика последнего сбора |
| `/history` | История последних 10 публикаций |
| `/help` | Справка |

Доступ только для пользователей из `ADMIN_IDS` в `.env`.

---

## Данные и хранение

Никакой базы данных не нужно. Всё хранится в папке `data/`:

- `data/events.json` — собранные события с дедупликацией
- `data/history.json` — история публикаций (дата, ID сообщения, количество событий)
- `data/stats.json` — статистика каждого запуска сбора

Для переноса на другой сервер достаточно скопировать:
```
.env
sources.json
telegram_session.session
data/          (опционально, если нужна история)
```

---

## Развёртывание на хостинге

### Вариант 1 — VPS (Ubuntu/Debian)

```bash
# 1. Установить Python
sudo apt update && sudo apt install python3 python3-venv python3-pip -y

# 2. Загрузить проект
git clone <репозиторий> bot_bali
cd bot_bali

# 3. Создать окружение и установить зависимости
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 4. Настроить .env (заполнить токены)
nano .env

# 5. Авторизовать Telethon (нужен интерактивный терминал)
venv/bin/python init_telegram_session.py

# 6. Запустить как systemd-сервис (автозапуск при перезагрузке)
sudo nano /etc/systemd/system/bot_bali.service
```

Содержимое `bot_bali.service`:

```ini
[Unit]
Description=Bali Real Estate Events Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/bot_bali
ExecStart=/home/ubuntu/bot_bali/venv/bin/python main.py
Restart=always
RestartSec=30
StandardOutput=append:/home/ubuntu/bot_bali/logs/bot.log
StandardError=append:/home/ubuntu/bot_bali/logs/bot.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable bot_bali
sudo systemctl start bot_bali

# Проверить статус
sudo systemctl status bot_bali

# Посмотреть логи
tail -f /home/ubuntu/bot_bali/logs/bot.log
```

### Вариант 2 — Railway / Render / Fly.io

Эти платформы поддерживают деплой из GitHub-репозитория.

**Важно:** `telegram_session.session` нельзя хранить в git (он в `.gitignore`). Нужно:
1. Авторизовать сессию локально
2. Загрузить файл `telegram_session.session` на сервер вручную через SSH или через переменную среды (base64)

**Procfile** для Railway/Render:
```
worker: python main.py
```

**Переменные окружения** задаются в панели платформы — не нужен файл `.env`.

### Вариант 3 — Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t bot_bali .
docker run -d \
  --name bot_bali \
  --restart always \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/telegram_session.session:/app/telegram_session.session \
  bot_bali
```

---

## Фильтры (config.py)

Ключевые слова можно редактировать в `config.py`:

```python
# Слова ВКЛЮЧЕНИЯ — должно быть хотя бы одно
INCLUDE_KEYWORDS = {
    "инвестиц", "недвижимост", "property", "real estate",
    "villa", "land", "roi", "yield", "rent", "аренда", ...
}

# Слова ИСКЛЮЧЕНИЯ — если есть, событие пропускается
EXCLUDE_KEYWORDS = {
    "вебинар", "webinar", "юрист", "миграц", "внж",
    "мастер-класс", "воркшоп", ...
}
```

---

## Расписание

Задаётся в `.env` в формате cron (UTC):

```env
COLLECTION_SCHEDULE=0 0 * * *    # сбор в 00:00 UTC = 08:00 WITA
PUBLICATION_SCHEDULE=0 1 * * *   # публикация в 01:00 UTC = 09:00 WITA
```

Для изменения расписания — отредактируй `.env` и перезапусти бота.

---

## Возможные проблемы

**Бот не отвечает / TimedOut**
→ Проверь `TELEGRAM_BOT_TOKEN` и доступность Telegram. Если запускаешь из России — нужен рабочий `PROXY_URL`.

**Парсер Telegram не работает**
→ Запусти `venv/bin/python init_telegram_session.py` заново для обновления сессии. Убедись что `TELEGRAM_API_ID` и `TELEGRAM_API_HASH` верные.

**Канал недоступен**
→ Убедись что Telegram-канал публичный (`t.me/channel_name` открывается в браузере).

**Нет событий в дайджесте**
→ Запусти `/collect` через admin-бота, потом `/stats` — посмотри сколько событий сохранено и сколько отфильтровано.
