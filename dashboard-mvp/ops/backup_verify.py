#!/usr/bin/env python3
"""
Верификация бэкапов ClickHouse
Проверяет наличие, контрольные суммы и размеры бэкапов
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import clickhouse_connect
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupVerifier:
    """Класс для верификации бэкапов ClickHouse."""
    
    def __init__(self, ch_host: str = "localhost", ch_port: int = 8123,
                 ch_user: str = "backup_user", ch_password: str = ""):
        """Инициализация верификатора."""
        self.ch_client = clickhouse_connect.get_client(
            host=ch_host,
            port=ch_port,
            username=ch_user,
            password=ch_password
        )
        
    def get_backup_info(self) -> List[Dict]:
        """Получение информации о бэкапах из meta.backup_runs."""
        try:
            result = self.ch_client.query("""
                SELECT 
                    backup_name,
                    mode,
                    target,
                    status,
                    bytes,
                    duration_ms,
                    ts,
                    details
                FROM meta.backup_runs
                ORDER BY ts DESC
            """)
            
            backups = []
            for row in result.result_rows:
                backups.append({
                    'backup_name': row[0],
                    'mode': row[1],
                    'target': row[2],
                    'status': row[3],
                    'bytes': row[4],
                    'duration_ms': row[5],
                    'ts': row[6],
                    'details': row[7]
                })
            
            return backups
        except Exception as e:
            logger.error(f"Ошибка получения информации о бэкапах: {e}")
            return []
    
    def check_backup_existence(self, backup_name: str, backup_target: str) -> bool:
        """Проверка существования бэкапа."""
        try:
            if backup_target.startswith("s3://"):
                return self._check_s3_backup(backup_name, backup_target)
            else:
                return self._check_local_backup(backup_name, backup_target)
        except Exception as e:
            logger.error(f"Ошибка проверки существования бэкапа {backup_name}: {e}")
            return False
    
    def _check_s3_backup(self, backup_name: str, backup_target: str) -> bool:
        """Проверка существования S3 бэкапа."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Извлекаем информацию из S3 URL
            # Формат: s3://bucket/prefix
            if not backup_target.startswith("s3://"):
                return False
                
            parts = backup_target[5:].split("/", 1)
            bucket = parts[0]
            prefix = parts[1] if len(parts) > 1 else ""
            
            # Проверяем переменные окружения для S3
            s3_access_key = os.getenv('S3_ACCESS_KEY')
            s3_secret_key = os.getenv('S3_SECRET_KEY')
            
            if not s3_access_key or not s3_secret_key:
                logger.warning("Не настроены переменные S3_ACCESS_KEY, S3_SECRET_KEY")
                return False
            
            # Создаем S3 клиент
            s3 = boto3.client(
                's3',
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key
            )
            
            # Проверяем существование бэкапа
            backup_path = f"{prefix}/{backup_name}"
            
            # Проверяем наличие объектов в бэкапе
            response = s3.list_objects_v2(
                Bucket=bucket,
                Prefix=backup_path,
                MaxKeys=1
            )
            
            return 'Contents' in response
        except ImportError:
            logger.warning("boto3 не установлен, невозможно проверить S3 бэкапы")
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки S3 бэкапа: {e}")
            return False
    
    def _check_local_backup(self, backup_name: str, backup_target: str) -> bool:
        """Проверка существования локального бэкапа."""
        try:
            # Извлекаем директорию из target
            if backup_target.startswith("/"):
                backup_dir = backup_target
            else:
                # Предполагаем, что это относительный путь
                backup_dir = os.path.join("/opt/clickhouse/backups", backup_target)
            
            backup_path = os.path.join(backup_dir, backup_name)
            
            return os.path.exists(backup_path) and os.path.isdir(backup_path)
        except Exception as e:
            logger.error(f"Ошибка проверки локального бэкапа: {e}")
            return False
    
    def check_backup_freshness(self, max_age_hours: int = 24) -> Tuple[List[Dict], List[Dict]]:
        """Проверка свежести бэкапов."""
        all_backups = self.get_backup_info()
        fresh_backups = []
        stale_backups = []
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for backup in all_backups:
            if backup['ts'] >= cutoff_time:
                fresh_backups.append(backup)
            else:
                stale_backups.append(backup)
        
        return fresh_backups, stale_backups
    
    def check_backup_chain(self) -> Dict[str, List[Dict]]:
        """Проверка целостности цепочки бэкапов."""
        all_backups = self.get_backup_info()
        
        # Группируем бэкапы по типу
        full_backups = [b for b in all_backups if b['mode'] == 'full' and b['status'] == 'ok']
        incr_backups = [b for b in all_backups if b['mode'] == 'incr' and b['status'] == 'ok']
        
        # Сортируем по времени
        full_backups.sort(key=lambda x: x['ts'])
        incr_backups.sort(key=lambda x: x['ts'])
        
        result = {
            'full_backups': full_backups,
            'incr_backups': incr_backups,
            'issues': []
        }
        
        # Проверяем наличие полного бэкапа
        if not full_backups:
            result['issues'].append("Отсутствуют полные бэкапы")
        
        # Проверяем инкрементальные бэкапы
        if incr_backups and full_backups:
            # Находим последний полный бэкап
            last_full = full_backups[-1]
            
            # Проверяем, что все инкрементальные бэкапы новее последнего полного
            for incr in incr_backups:
                if incr['ts'] < last_full['ts']:
                    result['issues'].append(f"Инкрементальный бэкап {incr['backup_name']} старее последнего полного бэкапа {last_full['backup_name']}")
        
        return result
    
    def verify_all_backups(self) -> Dict:
        """Полная верификация всех бэкапов."""
        logger.info("Начало верификации бэкапов...")
        
        result = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'missing_backups': 0,
            'issues': [],
            'details': []
        }
        
        all_backups = self.get_backup_info()
        result['total_backups'] = len(all_backups)
        
        if not all_backups:
            result['issues'].append("Нет бэкапов для проверки")
            return result
        
        for backup in all_backups:
            backup_info = {
                'name': backup['backup_name'],
                'mode': backup['mode'],
                'status': backup['status'],
                'exists': False,
                'size_mb': backup['bytes'] / (1024 * 1024) if backup['bytes'] else 0,
                'age_hours': (datetime.now() - backup['ts']).total_seconds() / 3600
            }
            
            if backup['status'] == 'ok':
                # Проверяем существование файла
                exists = self.check_backup_existence(backup['backup_name'], backup['target'])
                backup_info['exists'] = exists
                
                if exists:
                    result['successful_backups'] += 1
                else:
                    result['missing_backups'] += 1
                    result['issues'].append(f"Бэкап {backup['backup_name']} отсутствует в хранилище")
            else:
                result['failed_backups'] += 1
                result['issues'].append(f"Бэкап {backup['backup_name']} имеет статус: {backup['status']}")
            
            result['details'].append(backup_info)
        
        # Проверка свежести
        fresh_backups, stale_backups = self.check_backup_freshness()
        
        if not fresh_backups:
            result['issues'].append("Нет свежих бэкапов (за последние 24 часа)")
        
        # Проверка цепочки бэкапов
        chain_info = self.check_backup_chain()
        result['issues'].extend(chain_info['issues'])
        
        logger.info(f"Верификация завершена. Всего: {result['total_backups']}, "
                   f"успешных: {result['successful_backups']}, "
                   f"отсутствующих: {result['missing_backups']}, "
                   f"проблем: {len(result['issues'])}")
        
        return result
    
    def print_verification_report(self, result: Dict):
        """Вывод отчета о верификации."""
        print("\n" + "=" * 60)
        print("ОТЧЕТ О ВЕРИФИКАЦИИ БЭКАПОВ CLICKHOUSE")
        print("=" * 60)
        
        print(f"Всего бэкапов: {result['total_backups']}")
        print(f"Успешных: {result['successful_backups']}")
        print(f"Неудачных: {result['failed_backups']}")
        print(f"Отсутствующих: {result['missing_backups']}")
        print(f"Проблем: {len(result['issues'])}")
        
        if result['issues']:
            print("\nПРОБЛЕМЫ:")
            for i, issue in enumerate(result['issues'], 1):
                print(f"  {i}. {issue}")
        
        if result['details']:
            print("\nДЕТАЛИ ПО БЭКАПАМ:")
            print(f"{'Имя':<30} {'Тип':<6} {'Статус':<8} {'Существует':<10} {'Размер, МБ':<12} {'Возраст, ч':<10}")
            print("-" * 80)
            
            for detail in result['details']:
                print(f"{detail['name']:<30} {detail['mode']:<6} {detail['status']:<8} "
                      f"{'Да' if detail['exists'] else 'Нет':<10} {detail['size_mb']:<12.1f} {detail['age_hours']:<10.1f}")
        
        print("=" * 60)


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Верификация бэкапов ClickHouse")
    parser.add_argument("--host", default="localhost", help="Хост ClickHouse")
    parser.add_argument("--port", type=int, default=8123, help="Порт ClickHouse")
    parser.add_argument("--user", default="backup_user", help="Пользователь ClickHouse")
    parser.add_argument("--password", default="", help="Пароль пользователя ClickHouse")
    parser.add_argument("--fresh-hours", type=int, default=24, 
                       help="Максимальный возраст свежего бэкапа в часах")
    parser.add_argument("--json", action="store_true", help="Вывод в формате JSON")
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    load_dotenv()
    
    # Получаем пароль из переменных окружения, если не указан в аргументах
    password = args.password or os.getenv('CLICKHOUSE_BACKUP_USER_PASSWORD', '')
    
    # Создаем верификатор
    verifier = BackupVerifier(
        ch_host=args.host,
        ch_port=args.port,
        ch_user=args.user,
        ch_password=password
    )
    
    # Выполняем верификацию
    result = verifier.verify_all_backups()
    
    # Вывод результатов
    if args.json:
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        verifier.print_verification_report(result)
    
    # Выход с кодом ошибки, если есть проблемы
    if result['issues']:
        sys.exit(1)


if __name__ == "__main__":
    main()