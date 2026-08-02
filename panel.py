"""
Очень простая панель управления по ТЗ.
FastAPI веб-интерфейс для:
- Включение/выключение источников
- Ключевые слова / Анти-слова
- Расписание + кнопка "Обновить сейчас"
"""
import json
import os
from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
from datetime import datetime

# Импорты из нашего проекта
from database import SessionLocal
from collector import run_collection
from digest import compile_digest
from bot import publish_digest

app = FastAPI(title="Bali Real Estate Aggregator Panel")
templates = Jinja2Templates(directory="templates")

# Файл для хранения настроек
CONFIG_FILE = "panel_config.json"
SOURCES_FILE = "sources.json"

logger = logging.getLogger(__name__)

# ─── Стандартные настройки ────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "schedule_time": "09:00",  # WITA время
    "include_keywords": "инвестиции,недвижимость,property,real estate,development",
    "exclude_keywords": "вебинар,стрим,юрист,миграция,внж,мастер-класс",
    "last_run": None,
    "next_run": None,
}

DEFAULT_SOURCES = [
    # Предоставленные пользователем источники (по ТЗ)
    {"name": "Bali Invest", "type": "telegram", "enabled": True, "username": "bali_invest"},
    {"name": "Terra Auri", "type": "telegram", "enabled": True, "username": "terraauri"},
    {"name": "Venaso Bali", "type": "website", "enabled": True, "url": "https://venasobali.com.au/"},
    {"name": "PP Bali", "type": "website", "enabled": True, "url": "https://ppbali.com/"},
]


# ─── Вспомогательные функции ───────────────────────────────────────────────
def load_config():
    """Загрузить конфигурацию из файла."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфига: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Сохранить конфигурацию в файл."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения конфига: {e}")
        return False


def load_sources():
    """Загрузить список источников."""
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки источников: {e}")
    return DEFAULT_SOURCES.copy()


def save_sources(sources):
    """Сохранить список источников."""
    try:
        with open(SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения источников: {e}")
        return False


# ─── API endpoints ─────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def panel_home(request: Request):
    """Главная страница панели."""
    config = load_config()
    sources = load_sources()
    
    return templates.TemplateResponse("panel.html", {
        "request": request,
        "config": config,
        "sources": sources,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.get("/api/config")
async def get_config():
    """Получить текущую конфигурацию."""
    return load_config()


@app.post("/api/config")
async def update_config(
    schedule_time: str = Form(...),
    include_keywords: str = Form(...),
    exclude_keywords: str = Form(...),
):
    """Обновить конфигурацию."""
    config = load_config()
    config["schedule_time"] = schedule_time
    config["include_keywords"] = include_keywords
    config["exclude_keywords"] = exclude_keywords
    config["last_updated"] = datetime.now().isoformat()
    
    if save_config(config):
        return {"success": True, "message": "Конфигурация сохранена"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка сохранения конфигурации")


@app.post("/api/sources/add")
async def add_new_source(
    name: str = Form(...),
    source_type: str = Form(...),
    url_or_username: str = Form(None),
):
    """
    Добавить новый источник.
    По ТЗ: пользователь может вручную добавлять сайты, каналы и т.д.
    """
    # Проверяем тип источника
    valid_types = ["telegram", "website", "venasobali", "mirahdevelopments"]
    if source_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Неправильный тип источника. Допустимые: {', '.join(valid_types)}")
    
    # Проверяем обязательные поля
    if source_type in ["telegram", "website"] and not url_or_username:
        raise HTTPException(status_code=400, detail=f"Для типа '{source_type}' нужно указать URL или username")
    
    try:
        # Используем функцию из collector для добавления источника
        from collector import add_source
        success = add_source(source_type, name, url_or_username)
        
        if success:
            return {
                "success": True,
                "message": f"Источник '{name}' успешно добавлен",
                "type": source_type
            }
        else:
            raise HTTPException(status_code=400, detail="Не удалось добавить источник")
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении источника: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@app.post("/api/sources/{index}/delete")
async def delete_source(index: int):
    """Удалить источник по индексу."""
    sources = load_sources()
    
    if 0 <= index < len(sources):
        removed_source = sources.pop(index)
        if save_sources(sources):
            return {
                "success": True,
                "message": f"Источник '{removed_source.get('name')}' удалён"
            }
        else:
            raise HTTPException(status_code=500, detail="Ошибка сохранения изменений")
    else:
        raise HTTPException(status_code=404, detail="Источник не найден")


@app.get("/api/sources")
async def get_sources():
    """Получить список источников."""
    return load_sources()


@app.post("/api/sources/{index}/toggle")
async def toggle_source(index: int):
    """Включить/выключить источник."""
    sources = load_sources()
    if 0 <= index < len(sources):
        sources[index]["enabled"] = not sources[index].get("enabled", False)
        save_sources(sources)
        return {"success": True, "enabled": sources[index]["enabled"]}
    else:
        raise HTTPException(status_code=404, detail="Источник не найден")


@app.post("/api/run-now")
async def run_now():
    """
    Кнопка "Обновить сейчас" по ТЗ.
    Запускает сбор и публикацию немедленно.
    """
    config = load_config()
    
    try:
        # 1. Сбор данных
        logger.info("Ручной запуск по запросу из панели...")
        db = SessionLocal()
        stats = run_collection(db)
        db.close()
        
        # 2. Формирование дайджеста
        db = SessionLocal()
        digest_text = compile_digest(db)
        db.close()
        
        # 3. Публикация
        if digest_text:
            msg_id = await publish_digest(digest_text)
            if msg_id:
                config["last_run"] = datetime.now().isoformat()
                config["last_run_success"] = True
                save_config(config)
                return {
                    "success": True,
                    "message": f"Дайджест опубликован (ID: {msg_id})",
                    "stats": stats
                }
            else:
                config["last_run"] = datetime.now().isoformat()
                config["last_run_success"] = False
                save_config(config)
                return {
                    "success": False,
                    "message": "Публикация не удалась",
                    "stats": stats
                }
        else:
            return {
                "success": True,
                "message": "Нет событий для публикации",
                "stats": stats
            }
            
    except Exception as e:
        logger.error(f"Ошибка при ручном запуске: {e}", exc_info=True)
        config["last_run"] = datetime.now().isoformat()
        config["last_run_success"] = False
        save_config(config)
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.get("/api/status")
async def get_status():
    """Статус системы."""
    config = load_config()
    sources = load_sources()
    enabled_count = sum(1 for s in sources if s.get("enabled", False))
    
    return {
        "config": config,
        "sources_enabled": enabled_count,
        "sources_total": len(sources),
        "system_time": datetime.now().isoformat(),
    }


# ─── Шаблон HTML ───────────────────────────────────────────────────────────
if not os.path.exists("templates"):
    os.makedirs("templates")


with open("templates/panel.html", "w", encoding="utf-8") as f:
    f.write("""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bali Real Estate Aggregator Panel</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        .section {
            margin: 30px 0;
            padding: 20px;
            border-left: 4px solid #4CAF50;
            background: #f9f9f9;
        }
        .section h2 {
            color: #4CAF50;
            margin-top: 0;
        }
        input, textarea {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 0;
        }
        button:hover {
            background: #45a049;
        }
        .btn-run {
            background: #2196F3;
            font-size: 18px;
            padding: 15px 30px;
        }
        .btn-run:hover {
            background: #1976D2;
        }
        .source-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin: 5px 0;
            background: white;
            border: 1px solid #eee;
            border-radius: 5px;
        }
        .source-toggle {
            margin-right: 15px;
        }
        .source-info {
            flex: 1;
        }
        .source-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 10px;
        }
        .status-on {
            background: #4CAF50;
            color: white;
        }
        .status-off {
            background: #f44336;
            color: white;
        }
        .status {
            margin: 20px 0;
            padding: 15px;
            border-radius: 5px;
        }
        .status-success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .status-error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Панель управления Aggregator</h1>
        <p>Управление агрегатором событий по недвижимости на Бали</p>
        
        <!-- Статус -->
        <div id="status" class="status" style="display: none;"></div>
        
        <!-- Кнопка "Обновить сейчас" по ТЗ -->
        <div class="section">
            <h2>Быстрый запуск</h2>
            <button class="btn-run" onclick="runNow()">🔄 Обновить сейчас</button>
            <p><small>Запустит сбор из всех активных источников и опубликует дайджест</small></p>
        </div>
        
        <!-- Расписание -->
        <div class="section">
            <h2>Расписание</h2>
            <form id="scheduleForm">
                <label>Время дайджеста (WITA):</label>
                <input type="time" id="schedule_time" name="schedule_time" value="{{ config.schedule_time }}">
                <button type="submit">Сохранить</button>
            </form>
            <p><small>Текущее время: {{ now }}</small></p>
        </div>
        
        <!-- Ключевые слова -->
        <div class="section">
            <h2>Фильтры</h2>
            <form id="keywordsForm">
                <label>Ключевые слова (через запятую):</label>
                <textarea id="include_keywords" name="include_keywords" rows="3">{{ config.include_keywords }}</textarea>
                
                <label>Слова для исключения (через запятую):</label>
                <textarea id="exclude_keywords" name="exclude_keywords" rows="3">{{ config.exclude_keywords }}</textarea>
                
                <button type="submit">Сохранить фильтры</button>
            </form>
        </div>
        
        <!-- Источники -->
        <div class="section">
            <h2>Источники</h2>
            <p>Активных источников: <span id="enabledCount">{{ sources|selectattr('enabled')|list|length }}</span>/{{ sources|length }}</p>
            
            <div id="sourcesList">
                {% for source in sources %}
                <div class="source-item">
                    <div class="source-toggle">
                        <input type="checkbox" id="source{{ loop.index0 }}" 
                               onclick="toggleSource({{ loop.index0 }})"
                               {% if source.enabled %}checked{% endif %}>
                    </div>
                    <div class="source-info">
                        <strong>{{ source.name }}</strong>
                        <small>{{ source.type }}</small>
                    </div>
                    <div class="source-status {% if source.enabled %}status-on{% else %}status-off{% endif %}">
                        {% if source.enabled %}ВКЛ{% else %}ВЫКЛ{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <script>
        // Показать статус
        function showStatus(message, isSuccess) {
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + (isSuccess ? 'status-success' : 'status-error');
            statusDiv.style.display = 'block';
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 5000);
        }
        
        // Кнопка "Обновить сейчас"
        async function runNow() {
            try {
                const response = await fetch('/api/run-now', {
                    method: 'POST'
                });
                const result = await response.json();
                showStatus(result.message, result.success);
            } catch (error) {
                showStatus('Ошибка: ' + error.message, false);
            }
        }
        
        // Сохранить расписание
        document.getElementById('scheduleForm').onsubmit = async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                showStatus('Расписание сохранено', true);
            } catch (error) {
                showStatus('Ошибка сохранения', false);
            }
        };
        
        // Сохранить ключевые слова
        document.getElementById('keywordsForm').onsubmit = async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                showStatus('Фильтры сохранены', true);
            } catch (error) {
                showStatus('Ошибка сохранения', false);
            }
        };
        
        // Включить/выключить источник
        async function toggleSource(index) {
            try {
                const response = await fetch(`/api/sources/${index}/toggle`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                // Обновить статус в UI
                const sourceDiv = document.querySelector(`#sourcesList .source-item:nth-child(${index + 1})`);
                const statusSpan = sourceDiv.querySelector('.source-status');
                
                if (result.enabled) {
                    statusSpan.textContent = 'ВКЛ';
                    statusSpan.className = 'source-status status-on';
                } else {
                    statusSpan.textContent = 'ВЫКЛ';
                    statusSpan.className = 'source-status status-off';
                }
                
                // Обновить счетчик
                const enabledCount = document.querySelectorAll('.status-on').length;
                document.getElementById('enabledCount').textContent = enabledCount;
                
                showStatus('Источник обновлен', true);
            } catch (error) {
                showStatus('Ошибка обновления источника', false);
                // Вернуть чекбокс в исходное состояние
                const checkbox = document.getElementById(`source${index}`);
                checkbox.checked = !checkbox.checked;
            }
        }
    </script>
</body>
</html>""")

logger.info("Панель управления создана по ТЗ")


# ─── Запуск отдельно ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Запуск панели управления по ТЗ")
    print("=" * 60)
    print("Доступна по адресу: http://localhost:8000")
    print("Ctrl+C для остановки")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
