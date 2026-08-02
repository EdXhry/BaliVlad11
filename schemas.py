"""
Pydantic модели данных для Bali Events Aggregator.

Определяет схемы данных для:
- Event: структурированные данные о мероприятиях с валидацией
- RawEvent: неструктурированные данные из источников
- Digest: подборки мероприятий, готовые к публикации
- Configuration models: модели для конфигурационных файлов

Validates: Requirements 2.1-2.7, 3.1-3.3, 9.1-9.5
"""

from datetime import date, time, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Event(BaseModel):
    """
    Структурированные данные о мероприятии.
    
    Валидация согласно требованиям:
    - title: 3-200 символов (требование 3.1)
    - event_date: должна быть в будущем (требование 3.2)
    - location: обязательное поле (требование 3.3)
    """
    title: str = Field(min_length=3, max_length=200, description="Название мероприятия, 3-200 символов")
    event_date: date = Field(description="Дата проведения мероприятия")
    event_time: Optional[time] = Field(None, description="Время проведения мероприятия")
    location: str = Field(min_length=1, description="Место проведения (обязательно)")
    description: Optional[str] = Field(None, description="Описание мероприятия")
    source_url: str = Field(description="Ссылка на источник мероприятия")
    price: Optional[str] = Field(None, description="Стоимость входа (если доступна)")
    category: Optional[str] = Field(None, description="Категория мероприятия (музыка, спорт, искусство, образование)")
    
    @field_validator('event_date')
    @classmethod
    def date_must_be_future(cls, v: date) -> date:
        """Проверяет, что дата проведения находится в будущем."""
        if v < date.today():
            raise ValueError("Дата мероприятия должна быть в будущем")
        return v
    
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class RawEvent(BaseModel):
    """
    Неструктурированные данные о мероприятии из источников.
    
    Используется для хранения сырых данных до обработки.
    Все поля опциональны, так как разные источники могут предоставлять разную информацию.
    """
    raw_title: Optional[str] = Field(None, description="Необработанное название мероприятия")
    raw_date: Optional[str] = Field(None, description="Необработанная дата мероприятия")
    raw_time: Optional[str] = Field(None, description="Необработанное время мероприятия")
    raw_location: Optional[str] = Field(None, description="Необработанное место проведения")
    raw_description: Optional[str] = Field(None, description="Необработанное описание")
    raw_price: Optional[str] = Field(None, description="Необработанная информация о цене")
    raw_category: Optional[str] = Field(None, description="Необработанная категория")
    source_url: str = Field(description="URL источника данных")
    source_type: str = Field(description="Тип источника: website, api, social")
    collected_at: datetime = Field(default_factory=datetime.now, description="Время сбора данных")
    
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class Digest(BaseModel):
    """
    Подборка мероприятий, готовая к публикации.
    
    Содержит сгруппированные по датам мероприятия и
    отформатированный текст для публикации в Telegram.
    """
    period_from: date = Field(description="Начальная дата периода подборки")
    period_to: date = Field(description="Конечная дата периода подборки")
    events_by_date: Dict[date, List[Event]] = Field(description="Мероприятия, сгруппированные по датам")
    formatted_text: str = Field(description="Готовый Markdown текст для публикации в Telegram")
    
    @field_validator('period_to')
    @classmethod
    def validate_period(cls, v: date, info) -> date:
        """Проверяет, что period_to не раньше period_from."""
        period_from = info.data.get('period_from')
        if period_from and v < period_from:
            raise ValueError("period_to не может быть раньше period_from")
        return v
    
    model_config = ConfigDict(from_attributes=True)


# Модели конфигурации
class ParsingRules(BaseModel):
    """
    Правила парсинга для веб-сайтов.
    
    Определяет CSS-селекторы для извлечения полей мероприятий.
    """
    event_selector: str = Field(description="CSS-селектор для контейнера мероприятия")
    title_selector: str = Field(description="CSS-селектор для названия мероприятия")
    date_selector: str = Field(description="CSS-селектор для даты мероприятия")
    location_selector: str = Field(description="CSS-селектор для места проведения")
    description_selector: str = Field(description="CSS-селектор для описания мероприятия")
    price_selector: Optional[str] = Field(None, description="CSS-селектор для цены (опционально)")
    link_selector: str = Field(description="CSS-селектор для ссылки на мероприятие")
    
    model_config = ConfigDict(from_attributes=True)


class SourceAuth(BaseModel):
    """
    Конфигурация аутентификации для источников данных.
    
    Поддерживает различные типы аутентификации:
    - bearer: Bearer token
    - basic: Basic auth с username/password
    - api_key: API key в заголовке или параметре
    """
    type: str = Field(description="Тип аутентификации: bearer, basic, api_key")
    token: Optional[str] = Field(None, description="Bearer token или API key")
    username: Optional[str] = Field(None, description="Имя пользователя для basic auth")
    password: Optional[str] = Field(None, description="Пароль для basic auth")
    
    @field_validator('type')
    @classmethod
    def validate_auth_type(cls, v: str) -> str:
        """Проверяет валидность типа аутентификации."""
        valid_types = ['bearer', 'basic', 'api_key']
        if v not in valid_types:
            raise ValueError(f"Тип аутентификации должен быть одним из: {valid_types}")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class SourceConfig(BaseModel):
    """
    Конфигурация источника данных.
    
    Определяет настройки для каждого источника:
    - Тип источника (website, api, social)
    - URL или идентификатор
    - Правила парсинга (для веб-сайтов)
    - Аутентификация (если требуется)
    """
    name: str = Field(description="Название источника")
    type: str = Field(description="Тип источника: website, api, social")
    url: str = Field(description="URL источника или идентификатор (для социальных сетей)")
    enabled: bool = Field(True, description="Активен ли источник")
    parsing_rules: Optional[ParsingRules] = Field(None, description="Правила парсинга (для веб-сайтов)")
    auth: Optional[SourceAuth] = Field(None, description="Конфигурация аутентификации")
    
    @field_validator('type')
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Проверяет валидность типа источника."""
        valid_types = ['website', 'api', 'social']
        if v not in valid_types:
            raise ValueError(f"Тип источника должен быть одним из: {valid_types}")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class ScheduleConfig(BaseModel):
    """
    Конфигурация расписания.
    
    Определяет расписание для сбора данных и публикации подборок.
    Использует cron-формат для настройки времени запуска.
    """
    collection: Dict = Field(description="Расписание сбора данных (cron-формат)")
    publication: Dict = Field(description="Расписание публикации подборок (cron-формат)")
    
    @field_validator('collection', 'publication')
    @classmethod
    def validate_schedule_dict(cls, v: Dict) -> Dict:
        """Проверяет, что конфигурация расписания содержит необходимые поля."""
        if 'schedule' not in v:
            raise ValueError("Конфигурация расписания должна содержать поле 'schedule'")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class Configuration(BaseModel):
    """
    Корневая модель конфигурации приложения.
    
    Содержит все настройки для работы агента:
    - Telegram настройки
    - API настройки
    - Расписание
    - Фильтры
    - Список источников данных
    """
    telegram: Dict = Field(description="Настройки Telegram бота и канала")
    api: Dict = Field(description="Настройки HTTP API")
    scheduler: ScheduleConfig = Field(description="Конфигурация расписания")
    filters: Dict = Field(description="Настройки фильтров (категории и т.д.)")
    sources: List[SourceConfig] = Field(min_length=1, description="Список источников данных")
    
    @field_validator('telegram')
    @classmethod
    def validate_telegram_config(cls, v: Dict) -> Dict:
        """Проверяет обязательные поля для Telegram конфигурации."""
        required_fields = ['bot_token', 'channel_id']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Telegram конфигурация должна содержать поле '{field}'")
        return v
    
    @field_validator('api')
    @classmethod
    def validate_api_config(cls, v: Dict) -> Dict:
        """Проверяет обязательные поля для API конфигурации."""
        if 'token' not in v:
            raise ValueError("API конфигурация должна содержать поле 'token'")
        return v
    
    model_config = ConfigDict(from_attributes=True)