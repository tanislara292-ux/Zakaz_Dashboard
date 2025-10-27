"""
Клиент для работы с Google Sheets API.
Чтение данных из Google Sheets для интеграции QTickets.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Iterator
from datetime import datetime
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Настройка логгера
logger = logging.getLogger(__name__)

class GoogleSheetsClient:
    """Клиент для работы с Google Sheets API."""
    
    def __init__(self, credentials_path: str = None, scopes: List[str] = None):
        """
        Инициализация клиента Google Sheets.
        
        Args:
            credentials_path: Путь к JSON файлу с учетными данными сервисного аккаунта
            scopes: Список прав доступа для API
        """
        self.credentials_path = credentials_path or os.getenv('GSERVICE_JSON')
        self.scopes = scopes or ['https://www.googleapis.com/auth/spreadsheets.readonly']
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентификация в Google Sheets API."""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path, scopes=self.scopes
                )
            else:
                # Попытка использовать учетные данные по умолчанию
                credentials = google.auth.default(scopes=self.scopes)[0]
            
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Успешная аутентификация в Google Sheets API")
        except Exception as e:
            logger.error(f"Ошибка аутентификации в Google Sheets API: {e}")
            raise
    
    def read_sheet(self, spreadsheet_id: str, range_name: str, 
                   batch_size: int = 10000) -> Iterator[List[Dict[str, Any]]]:
        """
        Чтение данных из листа Google Sheets.
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            range_name: Диапазон для чтения (например, 'Sales!A:Z')
            batch_size: Размер пакета для чтения
            
        Yields:
            Список словарей с данными строк
        """
        try:
            # Сначала получаем заголовки
            header_result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{range_name.split('!')[0]}!1:1"
            ).execute()
            
            headers = header_result.get('values', [[]])[0]
            if not headers:
                logger.error(f"Не удалось получить заголовки из листа {range_name}")
                return
            
            # Нормализация заголовков (удаление пробелов, приведение к нижнему регистру)
            normalized_headers = [h.strip().lower() for h in headers]
            
            logger.info(f"Получены заголовки: {normalized_headers}")
            
            # Получаем общее количество строк
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            sheet_name = range_name.split('!')[0]
            for sheet in sheet_metadata.get('sheets', []):
                if sheet.get('properties', {}).get('title') == sheet_name:
                    total_rows = sheet.get('properties', {}).get('gridProperties', {}).get('rowCount', 0)
                    break
            else:
                total_rows = 1000  # Значение по умолчанию
            
            logger.info(f"Всего строк в листе {sheet_name}: {total_rows}")
            
            # Читаем данные пакетами
            start_row = 2  # Пропускаем заголовки
            while start_row <= total_rows:
                end_row = min(start_row + batch_size - 1, total_rows)
                current_range = f"{sheet_name}!A{start_row}:Z{end_row}"
                
                logger.debug(f"Чтение диапазона: {current_range}")
                
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=current_range
                ).execute()
                
                rows = result.get('values', [])
                if not rows:
                    logger.info(f"Нет данных в диапазоне {current_range}")
                    break
                
                # Преобразуем строки в словари
                batch_data = []
                for row in rows:
                    # Дополняем строку пустыми значениями, если она короче заголовков
                    row_extended = row + [''] * (len(normalized_headers) - len(row))
                    
                    row_dict = dict(zip(normalized_headers, row_extended))
                    batch_data.append(row_dict)
                
                yield batch_data
                
                start_row = end_row + 1
                
                # Если получили меньше строк, чем запрашивали, значит достигли конца
                if len(rows) < batch_size:
                    break
                    
        except HttpError as e:
            logger.error(f"Ошибка API Google Sheets: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при чтении листа {range_name}: {e}")
            raise
    
    def read_sheet_all(self, spreadsheet_id: str, range_name: str) -> List[Dict[str, Any]]:
        """
        Чтение всех данных из листа Google Sheets.
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            range_name: Диапазон для чтения
            
        Returns:
            Список словарей с данными строк
        """
        all_data = []
        for batch in self.read_sheet(spreadsheet_id, range_name):
            all_data.extend(batch)
        
        logger.info(f"Всего прочитано строк: {len(all_data)}")
        return all_data
    
    def validate_headers(self, spreadsheet_id: str, range_name: str, 
                        required_headers: List[str]) -> bool:
        """
        Проверка наличия обязательных заголовков в листе.
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            range_name: Диапазон для чтения
            required_headers: Список обязательных заголовков
            
        Returns:
            True если все заголовки присутствуют
        """
        try:
            header_result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{range_name.split('!')[0]}!1:1"
            ).execute()
            
            headers = [h.strip().lower() for h in header_result.get('values', [[]])[0]]
            required_lower = [h.lower() for h in required_headers]
            
            missing_headers = set(required_lower) - set(headers)
            
            if missing_headers:
                logger.error(f"Отсутствуют обязательные заголовки в листе {range_name}: {missing_headers}")
                logger.error(f"Найденные заголовки: {headers}")
                return False
            
            logger.info(f"Все обязательные заголовки присутствуют в листе {range_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке заголовков листа {range_name}: {e}")
            return False
    
    def get_sheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Получение информации о таблице.
        
        Args:
            spreadsheet_id: ID таблицы Google Sheets
            
        Returns:
            Словарь с информацией о таблице
        """
        try:
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            sheets_info = []
            for sheet in sheet_metadata.get('sheets', []):
                properties = sheet.get('properties', {})
                sheets_info.append({
                    'title': properties.get('title'),
                    'sheet_id': properties.get('sheetId'),
                    'row_count': properties.get('gridProperties', {}).get('rowCount'),
                    'column_count': properties.get('gridProperties', {}).get('columnCount')
                })
            
            return {
                'spreadsheet_id': spreadsheet_id,
                'title': sheet_metadata.get('properties', {}).get('title'),
                'sheets': sheets_info
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о таблице {spreadsheet_id}: {e}")
            return {}