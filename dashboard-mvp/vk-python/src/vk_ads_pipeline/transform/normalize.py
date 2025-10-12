"""Normalization utilities for VK Ads data."""

from __future__ import annotations

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def normalize_city_name(city: str) -> str:
    """Нормализация названия города."""
    if not city:
        return ""
    
    # Приводим к нижнему регистру и убираем пробелы
    normalized = city.lower().strip()
    
    # Заменяем ё на е
    normalized = normalized.replace('ё', 'е')
    
    # Убираем лишние пробелы и дефисы
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'-+', '-', normalized)
    
    # Убираем пробелы вокруг дефисов
    normalized = re.sub(r'\s*-\s*', '-', normalized)
    
    # Убираем спецсимволы, кроме пробелов и дефисов
    normalized = re.sub(r'[^\w\s\-]', '', normalized)
    
    return normalized.strip()


def extract_city(row: Dict[str, Any]) -> str:
    """Извлечение города из UTM-меток или названия объявления/кампании.
    
    Приоритет: utm_term → utm_campaign → adgroup_name → campaign_name.
    """
    # Проверяем utm_term
    city = row.get('utm_term', '')
    if city and _is_valid_city(city):
        return normalize_city_name(city)
    
    # Проверяем utm_campaign
    city = row.get('utm_campaign', '')
    if city and _is_valid_city(city):
        return normalize_city_name(city)
    
    # Проверяем adgroup_name
    city = row.get('adgroup_name', '')
    if city and _is_valid_city(city):
        return normalize_city_name(city)
    
    # Проверяем campaign_name
    city = row.get('campaign_name', '')
    if city and _is_valid_city(city):
        return normalize_city_name(city)
    
    # Проверяем city из API
    city = row.get('city', '')
    if city and _is_valid_city(city):
        return normalize_city_name(city)
    
    return ""


def _is_valid_city(city: str) -> bool:
    """Проверка, что строка может быть названием города."""
    if not city or len(city.strip()) < 2:
        return False
    
    # Простые паттерны для названий городов
    city_patterns = [
        r'москва|санкт-петербург|новосибирск|екатеринбург|нижний новгород|казань|челябинск|омск|самара|ростов-на-дону|уфа|красноярск|воронеж|пермь|волгоград',
        r'город|г\s+\w+',
        r'[а-яё\-]+\s*\([а-яё\-]+\)',  # Города с регионами в скобках
    ]
    
    city_lower = city.lower().strip()
    
    # Проверяем по известным паттернам
    for pattern in city_patterns:
        if re.search(pattern, city_lower):
            return True
    
    # Если город содержит только русские буквы, дефисы и пробелы
    if re.match(r'^[а-яё\s\-]+$', city_lower):
        # Исключаем слишком общие слова
        exclude_words = ['реклама', 'продвижение', 'маркетинг', 'продажи', 'акция', 'скидка']
        if city_lower not in exclude_words:
            return True
    
    return False


def normalize_vk_ads_row(row: Dict[str, Any], account_id: int) -> Dict[str, Any]:
    """Нормализация строки данных VK Ads для загрузки в ClickHouse."""
    normalized = row.copy()
    
    # Извлекаем город
    city_raw = extract_city(row)
    normalized['city'] = city_raw
    
    # Добавляем account_id
    normalized['account_id'] = account_id
    
    # Нормализуем UTM-метки
    for utm_field in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']:
        if utm_field in normalized:
            normalized[utm_field] = normalized[utm_field].lower().strip() if normalized[utm_field] else ""
    
    # Нормализуем числовые поля
    for num_field in ['impressions', 'clicks']:
        if num_field in normalized:
            try:
                normalized[num_field] = int(normalized[num_field] or 0)
            except (ValueError, TypeError):
                normalized[num_field] = 0
                logger.warning(f"Некорректное значение {num_field}: {row.get(num_field)}")
    
    # Нормализуем cost
    if 'cost' in normalized:
        try:
            normalized['cost'] = float(normalized['cost'] or 0)
        except (ValueError, TypeError):
            normalized['cost'] = 0.0
            logger.warning(f"Некорректное значение cost: {row.get('cost')}")
    
    # Нормализуем ID
    for id_field in ['campaign_id', 'adgroup_id']:
        if id_field in normalized:
            try:
                normalized[id_field] = int(normalized[id_field] or 0)
            except (ValueError, TypeError):
                normalized[id_field] = 0
                logger.warning(f"Некорректное значение {id_field}: {row.get(id_field)}")
    
    # Нормализуем дату
    if 'date' in normalized:
        date_str = normalized['date']
        if date_str and len(date_str) == 10:  # YYYY-MM-DD
            normalized['date'] = date_str
        else:
            logger.warning(f"Некорректный формат даты: {date_str}")
            normalized['date'] = ""
    
    return normalized