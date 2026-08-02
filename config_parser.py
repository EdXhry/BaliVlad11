"""
Парсер конфигурационных файлов для Bali Events Aggregator.

Реализует загрузку, валидацию и сериализацию конфигурационных файлов YAML
с использованием Pydantic моделей из schemas.py.

Validates: Requirements 10.1-10.4, 9.6
"""

import os
from typing import Union, Optional
import yaml
from pydantic import ValidationError

from schemas import Configuration


class ConfigParser:
    """
    Парсер конфигурационных файлов.

    Поддерживает:
    - Чтение и парсинг YAML файлов с валидацией через Pydantic
    - Сериализацию объектов Configuration обратно в YAML
    - Обработку ошибок с детальными сообщениями
    - File I/O операции
    """

    def __init__(self):
        """Инициализирует парсер конфигурации."""
        pass

    def parse(self, yaml_content: str) -> Configuration:
        """
        Парсит строку YAML и валидирует через Pydantic.

        Args:
            yaml_content: Строка с содержимым YAML конфигурации

        Returns:
            Объект Configuration, если конфигурация валидна

        Raises:
            ConfigError: При ошибках парсинга или валидации
        """
        try:
            # Парсинг YAML
            data = yaml.safe_load(yaml_content)
            if data is None:
                raise ConfigError("Конфигурационный файл пуст")
            
            # Валидация через Pydantic
            config = Configuration.model_validate(data)
            return config
            
        except yaml.YAMLError as e:
            # Детализация ошибки парсинга YAML
            error_msg = self._format_yaml_error(e, yaml_content)
            raise ConfigError(f"Ошибка синтаксиса YAML: {error_msg}")
        except ValidationError as e:
            # Детализация ошибки валидации Pydantic
            error_msg = self._format_validation_error(e)
            raise ConfigError(f"Ошибка валидации конфигурации: {error_msg}")
        except Exception as e:
            raise ConfigError(f"Неожиданная ошибка при парсинге: {str(e)}")

    def format(self, config: Configuration) -> str:
        """
        Сериализует объект Configuration обратно в YAML.

        Args:
            config: Объект Configuration для сериализации

        Returns:
            Строка с YAML конфигурацией

        Raises:
            ConfigError: При ошибках сериализации
        """
        try:
            # Преобразуем в dict
            data = config.model_dump(mode='json')
            
            # Сериализуем в YAML
            yaml_content = yaml.dump(
                data,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2
            )
            return yaml_content
            
        except Exception as e:
            raise ConfigError(f"Ошибка сериализации конфигурации: {str(e)}")

    def load_from_file(self, filepath: str) -> Configuration:
        """
        Загружает конфигурацию из файла.

        Args:
            filepath: Путь к конфигурационному файлу

        Returns:
            Объект Configuration

        Raises:
            ConfigError: При ошибках чтения файла или парсинга
        """
        try:
            # Проверка существования файла
            if not os.path.exists(filepath):
                raise ConfigError(f"Файл конфигурации не найден: {filepath}")
            
            # Чтение файла
            with open(filepath, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            
            # Парсинг
            return self.parse(yaml_content)
            
        except OSError as e:
            raise ConfigError(f"Ошибка чтения файла {filepath}: {str(e)}")
        except UnicodeDecodeError as e:
            raise ConfigError(f"Ошибка кодировки файла {filepath}: {str(e)}")

    def save_to_file(self, config: Configuration, filepath: str) -> None:
        """
        Сохраняет конфигурацию в файл.

        Args:
            config: Объект Configuration для сохранения
            filepath: Путь к файлу для сохранения

        Raises:
            ConfigError: При ошибках записи файла
        """
        try:
            # Форматирование в YAML
            yaml_content = self.format(config)
            
            # Создание директории, если не существует
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Запись в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
                
        except OSError as e:
            raise ConfigError(f"Ошибка записи файла {filepath}: {str(e)}")
        except Exception as e:
            raise ConfigError(f"Ошибка сохранения конфигурации: {str(e)}")

    def _format_yaml_error(self, error: yaml.YAMLError, yaml_content: str) -> str:
        """
        Форматирует сообщение об ошибке парсинга YAML.

        Args:
            error: Исключение YAMLError
            yaml_content: Исходный YAML контент

        Returns:
            Форматированное сообщение об ошибке
        """
        if hasattr(error, 'problem_mark'):
            mark = error.problem_mark
            line_num = mark.line + 1  # YAML использует 0-based индексы
            col_num = mark.column + 1
            
            # Получение строки с ошибкой
            lines = yaml_content.split('\n')
            if line_num - 1 < len(lines):
                error_line = lines[line_num - 1]
            else:
                error_line = "<конец файла>"
            
            return (f"Строка {line_num}, столбец {col_num}: {error.problem}\n"
                    f"Строка: '{error_line}'")
        else:
            return str(error)

    def _format_validation_error(self, error: ValidationError) -> str:
        """
        Форматирует сообщение об ошибке валидации Pydantic.

        Args:
            error: Исключение ValidationError

        Returns:
            Форматированное сообщение об ошибке
        """
        errors = []
        for err in error.errors():
            field = ' -> '.join(str(loc) for loc in err['loc'])
            msg = err['msg']
            error_type = err['type']
            
            # Добавление конкретных деталей для разных типов ошибок
            if error_type == 'value_error':
                if 'ctx' in err and 'error' in err['ctx']:
                    msg = err['ctx']['error']
            
            errors.append(f"Поле '{field}': {msg} ({error_type})")
        
        return "\n".join(errors)


class ConfigError(Exception):
    """
    Исключение для ошибок конфигурации.

    Содержит детальную информацию об ошибке для логирования и отладки.
    """
    pass


# Пример использования (для документации)
if __name__ == "__main__":
    # Пример YAML конфигурации
    example_yaml = """
telegram:
  bot_token: "BOT_TOKEN_HERE"
  channel_id: "@bali_events"

api:
  token: "SECRET_API_TOKEN"
  port: 8080

scheduler:
  collection:
    schedule: "0 9 * * *"
  publication:
    schedule: "0 10 * * 1,4"

filters:
  allowed_categories:
    - music
    - sport
    - art
    - education

sources:
  - name: "Bali Events Guide"
    type: website
    url: "https://balievents.com"
    enabled: true
    parsing_rules:
      event_selector: ".event-card"
      title_selector: "h2.event-title"
      date_selector: ".event-date"
      location_selector: ".event-venue"
      description_selector: ".event-description"
      link_selector: "a.event-link"
"""
    
    try:
        # Создание парсера
        parser = ConfigParser()
        
        # Парсинг конфигурации
        config = parser.parse(example_yaml)
        print("✅ Конфигурация успешно загружена")
        print(f"   Количество источников: {len(config.sources)}")
        
        # Сериализация обратно в YAML
        formatted = parser.format(config)
        print("✅ Конфигурация успешно сериализована")
        
        # Проверка round-trip свойства
        reparsed = parser.parse(formatted)
        if config == reparsed:
            print("✅ Round-trip свойство выполняется: config == parse(format(config))")
        else:
            print("❌ Round-trip свойство не выполняется")
            
    except ConfigError as e:
        print(f"❌ Ошибка конфигурации: {e}")