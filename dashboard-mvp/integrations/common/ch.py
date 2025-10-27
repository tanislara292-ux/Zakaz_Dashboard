"""
Общий модуль для работы с ClickHouse.
Предоставляет фабрику клиента с retry, verify TLS и чтением конфигурации.
"""

import os
import logging
import time
from typing import Optional, Dict, Any, List
import clickhouse_connect
from clickhouse_connect.driver.exceptions import ClickHouseError

# Import QticketsApiConfig for type hinting - will be imported at runtime

# Настройка логгера
logger = logging.getLogger(__name__)


class ClickHouseClient:
    """Клиент ClickHouse с retry и логированием."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        database: str = None,
        secure: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Инициализация клиента ClickHouse.

        Args:
            host: Хост сервера ClickHouse
            port: Порт сервера ClickHouse
            username: Имя пользователя
            password: Пароль
            database: Имя базы данных
            secure: Использовать HTTPS
            max_retries: Максимальное количество попыток подключения
            retry_delay: Задержка между попытками в секундах
        """
        self.host = host or os.getenv("CH_HOST", "localhost")
        self.port = port or int(os.getenv("CH_PORT", "8443" if secure else "9000"))
        self.username = username or os.getenv("CH_USER", "default")
        self.password = password or os.getenv("CH_PASSWORD", "")
        self.database = database or os.getenv("CH_DATABASE", "zakaz")
        self.secure = secure
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = None
        self._connect()

    def _connect(self):
        """Установка соединения с ClickHouse с retry."""
        for attempt in range(self.max_retries):
            try:
                self.client = clickhouse_connect.get_client(
                    host=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    database=self.database,
                    secure=self.secure,
                    verify=self.secure,
                    connect_timeout=10,
                    send_receive_timeout=30,
                )
                # Проверка соединения
                self.client.command("SELECT 1")
                logger.info(
                    f"Успешное подключение к ClickHouse: {self.host}:{self.port}"
                )
                return
            except Exception as e:
                logger.warning(
                    f"Попытка {attempt + 1}/{self.max_retries} подключения к ClickHouse не удалась: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Экспоненциальный бэкофф
                else:
                    logger.error(
                        f"Не удалось подключиться к ClickHouse после {self.max_retries} попыток"
                    )
                    raise

    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Выполнение SQL-запроса с retry.

        Args:
            query: SQL-запрос
            parameters: Параметры запроса

        Returns:
            Результат выполнения запроса
        """
        for attempt in range(self.max_retries):
            try:
                if parameters:
                    return self.client.query(query, parameters)
                else:
                    return self.client.query(query)
            except ClickHouseError as e:
                logger.warning(
                    f"Попытка {attempt + 1}/{self.max_retries} выполнения запроса не удалась: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    # Попытка переподключения
                    self._connect()
                else:
                    logger.error(
                        f"Не удалось выполнить запрос после {self.max_retries} попыток: {query[:100]}..."
                    )
                    raise
            except Exception as e:
                logger.error(f"Ошибка при выполнении запроса: {e}")
                # При проблемах с соединением пытаемся переподключиться
                if attempt < self.max_retries - 1:
                    self._connect()
                    time.sleep(self.retry_delay)
                else:
                    raise

    def insert(
        self,
        table: str,
        data: List[Dict[str, Any]],
        column_names: Optional[List[str]] = None,
    ) -> None:
        """
        Вставка данных в таблицу.

        Args:
            table: Имя таблицы
            data: Данные для вставки
            column_names: Имена колонок (опционально)
        """
        for attempt in range(self.max_retries):
            try:
                self.client.insert(table, data, column_names=column_names)
                logger.info(f"Успешная вставка {len(data)} строк в таблицу {table}")
                return
            except ClickHouseError as e:
                logger.warning(
                    f"Попытка {attempt + 1}/{self.max_retries} вставки данных не удалась: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    # Попытка переподключения
                    self._connect()
                else:
                    logger.error(
                        f"Не удалось вставить данные после {self.max_retries} попыток в таблицу {table}"
                    )
                    raise
            except Exception as e:
                logger.error(f"Ошибка при вставке данных: {e}")
                # При проблемах с соединением пытаемся переподключиться
                if attempt < self.max_retries - 1:
                    self._connect()
                    time.sleep(self.retry_delay)
                else:
                    raise

    def command(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Выполнение команды (без возврата данных).

        Args:
            query: SQL-команда
            parameters: Параметры команды

        Returns:
            Результат выполнения команды
        """
        for attempt in range(self.max_retries):
            try:
                if parameters:
                    return self.client.command(query, parameters)
                else:
                    return self.client.command(query)
            except ClickHouseError as e:
                logger.warning(
                    f"Попытка {attempt + 1}/{self.max_retries} выполнения команды не удалась: {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    # Попытка переподключения
                    self._connect()
                else:
                    logger.error(
                        f"Не удалось выполнить команду после {self.max_retries} попыток: {query[:100]}..."
                    )
                    raise
            except Exception as e:
                logger.error(f"Ошибка при выполнении команды: {e}")
                # При проблемах с соединением пытаемся переподключиться
                if attempt < self.max_retries - 1:
                    self._connect()
                    time.sleep(self.retry_delay)
                else:
                    raise


def get_client(env_file: Optional[str] = None) -> ClickHouseClient:
    """
    Фабрика для создания клиента ClickHouse с чтением конфигурации из .env файла.

    Args:
        env_file: Путь к .env файлу

    Returns:
        Экземпляр ClickHouseClient
    """
    if env_file:
        # Загрузка переменных окружения из файла
        from dotenv import load_dotenv

        load_dotenv(env_file)

    # Read connection parameters from environment
    host = os.getenv("CH_HOST", "localhost")
    port = int(os.getenv("CH_PORT", "8443"))
    username = os.getenv("CH_USER", "default")
    password = os.getenv("CH_PASSWORD", "")
    database = os.getenv("CH_DATABASE", "default")
    secure = os.getenv("CH_SECURE", "true").lower() in ("true", "1", "yes")
    verify_ssl = os.getenv("CH_VERIFY_SSL", "true").lower() in ("true", "1", "yes")

    return ClickHouseClient(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        secure=secure,
        max_retries=3,
        retry_delay=1.0,
    )


def get_client_from_config(cfg) -> ClickHouseClient:
    """
    Фабрика для создания клиента ClickHouse из объекта QticketsApiConfig.

    Args:
        cfg: Объект QticketsApiConfig с параметрами подключения

    Returns:
        Экземпляр ClickHouseClient
    """
    return ClickHouseClient(
        host=cfg.clickhouse_host,
        port=cfg.clickhouse_port,
        username=cfg.clickhouse_user,
        password=cfg.clickhouse_password,
        database=cfg.clickhouse_db,
        secure=cfg.clickhouse_secure,
        max_retries=3,
        retry_delay=1.0,
    )
