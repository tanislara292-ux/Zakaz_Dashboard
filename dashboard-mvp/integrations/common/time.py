"""
Общий модуль для работы с временными зонами и датами.
Поддерживает таймзону MSK (Europe/Moscow) и функции преобразования дат.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Union, Optional
import pytz

# Настройка логгера
logger = logging.getLogger(__name__)

# Таймзона по умолчанию - MSK
DEFAULT_TZ = os.getenv('DEFAULT_TZ', 'Europe/Moscow')
MSK_TZ = pytz.timezone(DEFAULT_TZ)

def now_msk() -> datetime:
    """
    Возвращает текущее время в таймзоне MSK.
    
    Returns:
        datetime: Текущее время в MSK
    """
    return datetime.now(MSK_TZ)

def today_msk() -> date:
    """
    Возвращает текущую дату в таймзоне MSK.
    
    Returns:
        date: Текущая дата в MSK
    """
    return now_msk().date()

def to_msk(dt: Union[datetime, str], fmt: Optional[str] = None) -> datetime:
    """
    Преобразует datetime или строку в таймзону MSK.
    
    Args:
        dt: datetime или строка с датой/временем
        fmt: Формат строки (если dt - строка)
        
    Returns:
        datetime: datetime в таймзоне MSK
    """
    if isinstance(dt, str):
        if fmt:
            dt = datetime.strptime(dt, fmt)
        else:
            # Попытка распарсить ISO формат
            try:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except ValueError:
                # Попытка распарсить другие форматы
                for f in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y']:
                    try:
                        dt = datetime.strptime(dt, f)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Не удалось распарсить дату: {dt}")
    
    # Если datetime без таймзоны, считаем что это UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    return dt.astimezone(MSK_TZ)

def to_date(dt: Union[datetime, str, date], fmt: Optional[str] = None) -> date:
    """
    Преобразует datetime, строку или date в date в таймзоне MSK.
    
    Args:
        dt: datetime, строка или date
        fmt: Формат строки (если dt - строка)
        
    Returns:
        date: Дата в MSK
    """
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt
    
    if isinstance(dt, str):
        dt = to_msk(dt, fmt)
    elif isinstance(dt, datetime):
        dt = to_msk(dt)
    
    return dt.date()

def date_range(start_date: Union[date, str, datetime], 
               end_date: Union[date, str, datetime]) -> list:
    """
    Генерирует список дат в диапазоне.
    
    Args:
        start_date: Начальная дата
        end_date: Конеч дата
        
    Returns:
        list: Список дат
    """
    if isinstance(start_date, str):
        start_date = to_date(start_date)
    elif isinstance(start_date, datetime):
        start_date = to_date(start_date)
        
    if isinstance(end_date, str):
        end_date = to_date(end_date)
    elif isinstance(end_date, datetime):
        end_date = to_date(end_date)
    
    delta = end_date - start_date
    return [start_date + timedelta(days=i) for i in range(delta.days + 1)]

def days_ago(days: int) -> date:
    """
    Возвращает дату N дней назад от текущей даты в MSK.
    
    Args:
        days: Количество дней назад
        
    Returns:
        date: Дата N дней назад
    """
    return today_msk() - timedelta(days=days)

def format_msk(dt: Union[datetime, date], fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Форматирует datetime или date в строку в таймзоне MSK.
    
    Args:
        dt: datetime или date
        fmt: Формат вывода
        
    Returns:
        str: Отформатированная строка
    """
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d')
    
    if isinstance(dt, datetime):
        dt = to_msk(dt)
    
    return dt.strftime(fmt)

def is_weekend(dt: Union[date, datetime]) -> bool:
    """
    Проверяет, является ли дата выходным днем.
    
    Args:
        dt: дата или datetime
        
    Returns:
        bool: True если выходной
    """
    if isinstance(dt, datetime):
        dt = dt.date()
    
    return dt.weekday() >= 5  # 5=Saturday, 6=Sunday

def parse_period(period_str: str) -> tuple:
    """
    Парсит строку периода и возвращает начальную и конечную дату.
    
    Args:
        period_str: Строка периода (например, "2023-10-01", "2023-10", "last_7_days")
        
    Returns:
        tuple: (start_date, end_date)
    """
    today = today_msk()
    
    if period_str == "today":
        return today, today
    elif period_str == "yesterday":
        return days_ago(1), days_ago(1)
    elif period_str == "last_7_days":
        return days_ago(6), today
    elif period_str == "last_30_days":
        return days_ago(29), today
    elif period_str == "this_month":
        start = today.replace(day=1)
        return start, today
    elif period_str == "last_month":
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
            end = date(today.year - 1, 12, 31)
        else:
            start = date(today.year, today.month - 1, 1)
            # Находим последний день предыдущего месяца
            if today.month == 2:
                end = date(today.year, 2, 28 if today.year % 4 != 0 or (today.year % 100 == 0 and today.year % 400 != 0) else 29)
            else:
                end = date(today.year, today.month, 1) - timedelta(days=1)
        return start, end
    else:
        # Попытка распарсить конкретную дату или диапазон
        if len(period_str) == 7:  # YYYY-MM
            year, month = map(int, period_str.split('-'))
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            return start, end
        elif len(period_str) == 10:  # YYYY-MM-DD
            start = to_date(period_str)
            return start, start
        else:
            raise ValueError(f"Неподдерживаемый формат периода: {period_str}")