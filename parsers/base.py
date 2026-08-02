"""
Базовый класс для всех парсеров.
Содержит общую логику: HTTP запросы, retry, логирование.
"""
import httpx
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Генератор случайных User-Agent (чтобы сайты не блокировали)
ua = UserAgent()


@dataclass
class RawEvent:
    """Сырые данные о мероприятии до обработки."""
    title: str
    event_date: date
    location: str
    source_url: str
    source_name: str
    event_time: Optional[time] = None
    description: Optional[str] = None
    price: Optional[str] = None
    category: Optional[str] = None
    speakers: Optional[str] = None  # Спикеры мероприятия
    language: Optional[str] = None  # Язык (ru, en, ru+en)
    is_online: Optional[bool] = None  # Онлайн или оффлайн
    event_type: Optional[str] = None  # Тип мероприятия


class BaseParser(ABC):
    """
    Базовый парсер. Все конкретные парсеры наследуются от него.
    
    Использует:
    - httpx для HTTP запросов (async-friendly, лучше чем requests)
    - tenacity для автоматических повторных попыток
    - fake_useragent для смены User-Agent
    """

    # Таймаут для каждого запроса (секунды)
    TIMEOUT = 30
    # Максимум попыток при ошибке
    MAX_RETRIES = 3
    # Задержка между попытками (секунды)
    RETRY_DELAY = 5

    def __init__(self):
        self.client = httpx.Client(
            timeout=httpx.Timeout(self.TIMEOUT),
            follow_redirects=True,
            headers={"User-Agent": ua.random}
        )

    def _get(self, url: str, params: dict = None) -> httpx.Response:
        """
        HTTP GET запрос с retry логикой.
        
        - При 5xx ошибке: повторит через RETRY_DELAY секунд (до MAX_RETRIES раз)
        - При 403/4xx ошибке: сразу возвращает None — не имеет смысла повторять
        - При timeout: повторит попытку
        """
        @retry(
            stop=stop_after_attempt(self.MAX_RETRIES),
            wait=wait_fixed(self.RETRY_DELAY),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
            reraise=True
        )
        def _do_request():
            self.client.headers["User-Agent"] = ua.random  # Меняем каждый раз
            response = self.client.get(url, params=params)

            if response.status_code == 403:
                # Сайт заблокировал парсер — молча пропускаем, не спамим в лог
                logger.debug(f"403 Forbidden: {url} — сайт блокирует парсер, пропускаем")
                raise httpx.HTTPStatusError(
                    f"403 Forbidden",
                    request=response.request,
                    response=response
                )
            elif response.status_code >= 500:
                logger.warning(f"Ошибка сервера {response.status_code} при запросе {url}, повтор...")
                raise httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response
                )
            elif response.status_code >= 400:
                logger.warning(f"Ошибка клиента {response.status_code} при запросе {url}, пропускаем")
                response.raise_for_status()

            return response

        return _do_request()

    @abstractmethod
    def parse(self) -> list[RawEvent]:
        """
        Главный метод парсинга. Каждый парсер реализует его по-своему.
        Возвращает список RawEvent объектов.
        """
        pass

    def close(self):
        """Закрыть HTTP клиент."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
