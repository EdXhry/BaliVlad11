# Быстрый старт - Bali Real Estate Aggregator

## Установка и запуск

### 1. Установка зависимостей

```bash
# Активировать виртуальное окружение
venv\Scripts\activate  # Windows
# или
source venv/bin/activate  # Linux/Mac

# Установить зависимости
pip install -e .
```

### 2. Настройка базы данных

```bash
# Создать базу данных PostgreSQL
createdb bali_events

# Или через psql:
# psql -U postgres
# CREATE DATABASE bali_events;
```

### 3. Настройка .env

Убедитесь, что файл `.env` содержит:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHANNEL_ID=@your_channel
PROXY_URL=http://user:password@ip:port
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/bali_events
```

### 4. Проверка работы

```bash
# Тест подключения к Telegram
python main.py test-bot

# Тест парсинга источников
python test_parsing.py
```

### 5. Запуск

#### Вариант 1: Планировщик (автоматический)

```bash
python main.py
```

- Автоматический сбор в 00:00 UTC (08:00 WITA)
- Автоматическая публикация в 01:00 UTC (09:00 WITA)

#### Вариант 2: Панель управления (ручной)

```bash
python panel.py
```

- Откроется веб-интерфейс на http://localhost:8000
- Кнопка "Обновить сейчас" для ручного запуска
- Управление источниками, фильтрами, расписанием

#### Вариант 3: Ручные команды

```bash
# Сбор данных
python main.py collect

# Публикация дайджеста
python main.py publish
```

## Источники данных

Настроены в файле `sources.json`:

1. **@bali_invest** (Telegram) - инвестиции в недвижимость на Бали
2. **@terraauri** (Telegram) - недвижимость и инвестиции
3. **venasobali.com.au** (Website) - недвижимость на Бали
4. **ppbali.com** (Website) - недвижимость на Бали

## Добавление новых источников

### Через панель управления:

1. Откройте http://localhost:8000
2. Заполните форму "Добавить новый источник"
3. Укажите:
   - Название источника
   - Тип: Telegram или Website
   - URL (для сайта) или username (для Telegram)

### Через файл sources.json:

```json
{
  "name": "Название источника",
  "type": "telegram",  // или "website"
  "username": "channel_name",  // для Telegram
  "url": "https://example.com/",  // для website
  "enabled": true
}
```

## Формат дайджеста

По ТЗ, каждое событие выводится в формате:

```
📅 26 июня, 14:00 WITA
📍 Canggu, Bali
🏷 ОФФЛАЙН | Тип: встреча
🧵 Инвестиционный митап: недвижимость на Бали
🗣 Иван Петров / Bali Property Group
Язык: 🇷🇺 RU
🔗 [Подробнее](ссылка)
```

## Фильтрация

### Включать (тема):
- инвестиции, недвижимость, property, real estate
- development, ROI, yield, rent, villa, land
- property management, coliving, strata, налоги

### Исключать:
- вебинар, webinar, стрим, stream
- онлайн-only, zoom-only
- юрист, миграция, ВНЖ

### Гео-фильтр (для оффлайн):
- Bali, Denpasar, Canggu, Ubud, Seminyak
- Sanur, Kuta, Jimbaran, Uluwatu, Nusa Dua, Bukit

## Расписание

- **Сбор данных**: 08:00 WITA (00:00 UTC)
- **Публикация**: 09:00 WITA (01:00 UTC)

Можно изменить в `.env`:

```env
COLLECTION_SCHEDULE=0 0 * * *
PUBLICATION_SCHEDULE=0 1 * * *
```

## Устранение проблем

### Ошибка подключения к Telegram
```
❌ Network error
```
**Решение**: Проверьте прокси в `.env`

### Бот не может отправить в канал
```
❌ Forbidden: bot is not a member of the channel
```
**Решение**: Добавьте бота как администратора в канал

### Ошибка подключения к БД
```
❌ Connection refused
```
**Решение**: Убедитесь, что PostgreSQL запущен и база создана

### Нет событий при парсинге
**Решение**: Проверьте логи в `bot_bali.log`, возможно изменилась структура сайтов

## Логи

Все логи сохраняются в `bot_bali.log`:

```bash
# Просмотр логов
Get-Content bot_bali.log -Tail 50  # Windows PowerShell
tail -f bot_bali.log               # Linux/Mac
```

## Тестирование

```bash
# Тест парсинга всех источников
python test_parsing.py

# Тест бота
python main.py test-bot

# Ручной сбор
python main.py collect
```
