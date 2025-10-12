"""
Общий модуль для логирования.
Предоставляет единый формат логов и метрики.
"""

import os
import sys
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

# Настройка логгера
logger = logging.getLogger(__name__)

# Уровни логирования
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

class Metrics:
    """Класс для сбора метрик."""
    
    def __init__(self):
        self.metrics = {}
    
    def increment(self, metric_name: str, value: int = 1):
        """Увеличивает значение метрики."""
        self.metrics[metric_name] = self.metrics.get(metric_name, 0) + value
    
    def set(self, metric_name: str, value: Any):
        """Устанавливает значение метрики."""
        self.metrics[metric_name] = value
    
    def get(self, metric_name: str) -> Any:
        """Получает значение метрики."""
        return self.metrics.get(metric_name)
    
    def get_all(self) -> Dict[str, Any]:
        """Получает все метрики."""
        return self.metrics.copy()
    
    def reset(self):
        """Сбрасывает все метрики."""
        self.metrics.clear()

class JSONFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Добавляем метрики, если они есть
        if hasattr(record, 'metrics'):
            log_entry['metrics'] = record.metrics
        
        # Добавляем исключение, если есть
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

class StructuredLogger:
    """Структурированный логгер с метриками."""
    
    def __init__(self, name: str, level: str = 'INFO', 
                 json_output: bool = False, 
                 log_file: Optional[str] = None):
        """
        Инициализация структурированного логгера.
        
        Args:
            name: Имя логгера
            level: Уровень логирования
            json_output: Использовать JSON формат
            log_file: Файл для записи логов
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        
        # Очистка существующих обработчиков
        self.logger.handlers.clear()
        
        # Форматтер
        if json_output:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Обработчик для консоли
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Обработчик для файла
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        self.metrics = Metrics()
    
    def _log_with_metrics(self, level: int, message: str, 
                         metrics: Optional[Dict[str, Any]] = None,
                         exc_info: Optional[bool] = None):
        """Логирование с метриками."""
        if metrics:
            # Объединяем с текущими метриками
            all_metrics = self.metrics.get_all()
            all_metrics.update(metrics)
        else:
            all_metrics = self.metrics.get_all()
        
        # Создаем запись с метриками
        record = self.logger.makeRecord(
            self.logger.name, level, '', 0, message, (), None
        )
        record.metrics = all_metrics
        
        if exc_info:
            record.exc_info = sys.exc_info()
        
        self.logger.handle(record)
    
    def debug(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """DEBUG уровень логирования."""
        self._log_with_metrics(logging.DEBUG, message, metrics)
    
    def info(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """INFO уровень логирования."""
        self._log_with_metrics(logging.INFO, message, metrics)
    
    def warning(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """WARNING уровень логирования."""
        self._log_with_metrics(logging.WARNING, message, metrics)
    
    def error(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """ERROR уровень логирования."""
        self._log_with_metrics(logging.ERROR, message, metrics)
    
    def critical(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """CRITICAL уровень логирования."""
        self._log_with_metrics(logging.CRITICAL, message, metrics)
    
    def exception(self, message: str, metrics: Optional[Dict[str, Any]] = None):
        """Логирование исключения."""
        self._log_with_metrics(logging.ERROR, message, metrics, exc_info=True)

def get_logger(name: str, level: str = 'INFO', 
               json_output: bool = False,
               log_file: Optional[str] = None) -> StructuredLogger:
    """
    Фабрика для создания структурированного логгера.
    
    Args:
        name: Имя логгера
        level: Уровень логирования
        json_output: Использовать JSON формат
        log_file: Файл для записи логов
        
    Returns:
        StructuredLogger экземпляр
    """
    return StructuredLogger(name, level, json_output, log_file)

def log_execution_time(logger: StructuredLogger):
    """
    Декоратор для логирования времени выполнения функции.
    
    Args:
        logger: Экземпляр StructuredLogger
        
    Returns:
        Декорированная функция
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"
            
            logger.info(f"Начало выполнения: {function_name}")
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(
                    f"Успешное завершение: {function_name}",
                    metrics={
                        'execution_time_seconds': round(execution_time, 2),
                        'function_name': function_name,
                        'status': 'success'
                    }
                )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.exception(
                    f"Ошибка при выполнении: {function_name}",
                    metrics={
                        'execution_time_seconds': round(execution_time, 2),
                        'function_name': function_name,
                        'status': 'error',
                        'error_type': type(e).__name__
                    }
                )
                
                raise
        
        return wrapper
    return decorator

def log_data_operation(logger: StructuredLogger, operation: str, 
                      source: str, target: str):
    """
    Декоратор для логирования операций с данными.
    
    Args:
        logger: Экземпляр StructuredLogger
        operation: Тип операции (load, extract, transform)
        source: Источник данных
        target: Цель данных
        
    Returns:
        Декорированная функция
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{func.__module__}.{func.__name__}"
            
            logger.info(
                f"Начало операции {operation}: {source} -> {target}",
                metrics={
                    'operation': operation,
                    'source': source,
                    'target': target,
                    'function_name': function_name
                }
            )
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Определяем количество обработанных строк
                rows_processed = 0
                if isinstance(result, (list, tuple)):
                    rows_processed = len(result)
                elif isinstance(result, dict) and 'rows' in result:
                    rows_processed = result['rows']
                
                logger.info(
                    f"Успешное завершение операции {operation}: {source} -> {target}",
                    metrics={
                        'operation': operation,
                        'source': source,
                        'target': target,
                        'rows_processed': rows_processed,
                        'execution_time_seconds': round(execution_time, 2),
                        'function_name': function_name,
                        'status': 'success'
                    }
                )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.exception(
                    f"Ошибка при выполнении операции {operation}: {source} -> {target}",
                    metrics={
                        'operation': operation,
                        'source': source,
                        'target': target,
                        'execution_time_seconds': round(execution_time, 2),
                        'function_name': function_name,
                        'status': 'error',
                        'error_type': type(e).__name__
                    }
                )
                
                raise
        
        return wrapper
    return decorator

def setup_integrations_logger(name: str, log_file: Optional[str] = None) -> StructuredLogger:
    """
    Настройка логгера для интеграций.
    
    Args:
        name: Имя логгера
        log_file: Файл для записи логов
        
    Returns:
        StructuredLogger экземпляр
    """
    # Получаем настройки из переменных окружения
    level = os.getenv('LOG_LEVEL', 'INFO')
    json_output = os.getenv('LOG_JSON', 'false').lower() == 'true'
    
    if not log_file:
        log_file = os.getenv('LOG_FILE')
    
    return get_logger(name, level, json_output, log_file)