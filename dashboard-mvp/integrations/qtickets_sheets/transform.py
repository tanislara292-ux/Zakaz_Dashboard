"""
Модуль для трансформации и нормализации данных из Google Sheets.
"""

import os
import hashlib
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from decimal import Decimal, InvalidOperation

# Настройка логгера
logger = logging.getLogger(__name__)

class DataTransformer:
    """Класс для трансформации данных из Google Sheets."""
    
    def __init__(self, timezone: str = 'Europe/Moscow'):
        """
        Инициализация трансформера.
        
        Args:
            timezone: Таймзона для преобразования дат
        """
        self.timezone = timezone
        self.key_fields = {
            'sales': os.getenv('KEY_SALES', 'date|event_id|city').split('|'),
            'events': os.getenv('KEY_EVENTS', 'event_id|event_date|city').split('|'),
            'inventory': os.getenv('KEY_INVENTORY', 'event_id|city').split('|')
        }
    
    def normalize_string(self, value: Any) -> str:
        """
        Нормализация строки: удаление пробелов, приведение к нижнему регистру.
        
        Args:
            value: Значение для нормализации
            
        Returns:
            Нормализованная строка
        """
        if value is None:
            return ""
        
        return str(value).strip()
    
    def normalize_city(self, value: Any) -> str:
        """
        Нормализация названия города.
        
        Args:
            value: Название города
            
        Returns:
            Нормализованное название города
        """
        return self.normalize_string(value).lower()
    
    def normalize_date(self, value: Any, input_format: str = None) -> Optional[date]:
        """
        Нормализация даты.
        
        Args:
            value: Значение даты
            input_format: Формат входной даты (если None, пытается угадать)
            
        Returns:
            Нормализованная дата или None в случае ошибки
        """
        if value is None or value == "":
            return None
        
        value_str = str(value).strip()
        
        # Если уже в формате YYYY-MM-DD
        if len(value_str) == 10 and value_str[4] == '-' and value_str[7] == '-':
            try:
                return datetime.strptime(value_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # Пробуем различные форматы
        formats_to_try = [
            '%d.%m.%Y',    # DD.MM.YYYY
            '%d/%m/%Y',    # DD/MM/YYYY
            '%Y-%m-%d',    # YYYY-MM-DD
            '%m/%d/%Y',    # MM/DD/YYYY
        ]
        
        if input_format:
            formats_to_try.insert(0, input_format)
        
        for fmt in formats_to_try:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue
        
        logger.warning(f"Не удалось распарсить дату: {value_str}")
        return None
    
    def normalize_number(self, value: Any, default: int = 0) -> int:
        """
        Нормализация числового значения.
        
        Args:
            value: Значение для нормализации
            default: Значение по умолчанию
            
        Returns:
            Нормализованное число
        """
        if value is None or value == "":
            return default
        
        try:
            # Удаляем пробелы и нечисловые символы (кроме точки и запятой)
            value_str = str(value).replace(' ', '').replace(',', '.')
            return int(float(value_str))
        except (ValueError, TypeError):
            logger.warning(f"Не удалось преобразовать в число: {value}, используем значение по умолчанию: {default}")
            return default
    
    def normalize_decimal(self, value: Any, default: float = 0.0) -> float:
        """
        Нормализация десятичного значения.
        
        Args:
            value: Значение для нормализации
            default: Значение по умолчанию
            
        Returns:
            Нормализованное десятичное число
        """
        if value is None or value == "":
            return default
        
        try:
            # Удаляем пробелы и заменяем запятую на точку
            value_str = str(value).replace(' ', '').replace(',', '.')
            return float(value_str)
        except (ValueError, TypeError):
            logger.warning(f"Не удалось преобразовать в десятичное число: {value}, используем значение по умолчанию: {default}")
            return default
    
    def generate_hash(self, data: Dict[str, Any], key_fields: List[str]) -> str:
        """
        Генерация хэша для идентификации дубликатов.
        
        Args:
            data: Словарь с данными
            key_fields: Список полей для ключа
            
        Returns:
            SHA256 хэш
        """
        key_values = []
        for field in key_fields:
            value = data.get(field, '')
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            key_values.append(str(value))
        
        key_string = '|'.join(key_values)
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    def transform_event(self, raw_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Трансформация данных мероприятия.
        
        Args:
            raw_event: Сырые данные мероприятия
            
        Returns:
            Трансформированные данные или None в случае ошибки
        """
        try:
            event_id = self.normalize_string(raw_event.get('event_id'))
            if not event_id:
                logger.warning("Пропуск мероприятия: отсутствует event_id")
                return None
            
            event_date = self.normalize_date(raw_event.get('event_date'))
            if not event_date:
                logger.warning(f"Пропуск мероприятия {event_id}: отсутствует или некорректная event_date")
                return None
            
            city = self.normalize_city(raw_event.get('city'))
            if not city:
                logger.warning(f"Пропуск мероприятия {event_id}: отсутствует city")
                return None
            
            transformed = {
                'event_id': event_id,
                'event_name': self.normalize_string(raw_event.get('event_name')),
                'event_date': event_date,
                'city': city,
                'tickets_total': self.normalize_number(raw_event.get('tickets_total')),
                'tickets_left': self.normalize_number(raw_event.get('tickets_left')),
                '_ver': int(datetime.now().timestamp()),
                'hash_low_card': self.generate_hash(raw_event, self.key_fields['events'])
            }
            
            return transformed
            
        except Exception as e:
            logger.error(f"Ошибка при трансформации мероприятия: {e}")
            return None
    
    def transform_inventory(self, raw_inventory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Трансформация данных инвентаря.
        
        Args:
            raw_inventory: Сырые данные инвентаря
            
        Returns:
            Трансформированные данные или None в случае ошибки
        """
        try:
            event_id = self.normalize_string(raw_inventory.get('event_id'))
            if not event_id:
                logger.warning("Пропуск инвентаря: отсутствует event_id")
                return None
            
            city = self.normalize_city(raw_inventory.get('city'))
            if not city:
                logger.warning(f"Пропуск инвентаря {event_id}: отсутствует city")
                return None
            
            transformed = {
                'event_id': event_id,
                'city': city,
                'tickets_total': self.normalize_number(raw_inventory.get('tickets_total')),
                'tickets_left': self.normalize_number(raw_inventory.get('tickets_left')),
                '_ver': int(datetime.now().timestamp()),
                'hash_low_card': self.generate_hash(raw_inventory, self.key_fields['inventory'])
            }
            
            return transformed
            
        except Exception as e:
            logger.error(f"Ошибка при трансформации инвентаря: {e}")
            return None
    
    def transform_sale(self, raw_sale: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Трансформация данных продажи.
        
        Args:
            raw_sale: Сырые данные продажи
            
        Returns:
            Трансформированные данные или None в случае ошибки
        """
        try:
            sale_date = self.normalize_date(raw_sale.get('date'))
            if not sale_date:
                logger.warning("Пропуск продажи: отсутствует или некорректная date")
                return None
            
            event_id = self.normalize_string(raw_sale.get('event_id'))
            if not event_id:
                logger.warning("Пропуск продажи: отсутствует event_id")
                return None
            
            city = self.normalize_city(raw_sale.get('city'))
            if not city:
                logger.warning(f"Пропуск продажи {event_id}: отсутствует city")
                return None
            
            transformed = {
                'date': sale_date,
                'event_id': event_id,
                'event_name': self.normalize_string(raw_sale.get('event_name')),
                'city': city,
                'tickets_sold': self.normalize_number(raw_sale.get('tickets_sold')),
                'revenue': self.normalize_decimal(raw_sale.get('revenue')),
                'refunds': self.normalize_decimal(raw_sale.get('refunds', 0)),
                'currency': self.normalize_string(raw_sale.get('currency', 'RUB')),
                '_ver': int(datetime.now().timestamp()),
                'hash_low_card': self.generate_hash(raw_sale, self.key_fields['sales'])
            }
            
            return transformed
            
        except Exception as e:
            logger.error(f"Ошибка при трансформации продажи: {e}")
            return None
    
    def transform_events(self, raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Трансформация списка мероприятий.
        
        Args:
            raw_events: Список сырых данных мероприятий
            
        Returns:
            Список трансформированных данных
        """
        transformed = []
        for raw_event in raw_events:
            event = self.transform_event(raw_event)
            if event:
                transformed.append(event)
        
        logger.info(f"Трансформировано мероприятий: {len(transformed)} из {len(raw_events)}")
        return transformed
    
    def transform_inventory(self, raw_inventory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Трансформация списка инвентаря.
        
        Args:
            raw_inventory: Список сырых данных инвентаря
            
        Returns:
            Список трансформированных данных
        """
        transformed = []
        for raw_item in raw_inventory:
            item = self.transform_inventory(raw_item)
            if item:
                transformed.append(item)
        
        logger.info(f"Трансформировано записей инвентаря: {len(transformed)} из {len(raw_inventory)}")
        return transformed
    
    def transform_sales(self, raw_sales: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Трансформация списка продаж.
        
        Args:
            raw_sales: Список сырых данных продаж
            
        Returns:
            Список трансформированных данных
        """
        transformed = []
        for raw_sale in raw_sales:
            sale = self.transform_sale(raw_sale)
            if sale:
                transformed.append(sale)
        
        logger.info(f"Трансформировано продаж: {len(transformed)} из {len(raw_sales)}")
        return transformed