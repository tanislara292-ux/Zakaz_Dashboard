#!/usr/bin/env python3
"""
SLO Guard - мониторинг и алерты при нарушении SLO.
"""
import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional

import clickhouse_connect
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SLOGuard:
    """Класс для мониторинга SLO и отправки алертов."""
    
    def __init__(self):
        """Инициализация SLO Guard."""
        load_dotenv()
        
        # ClickHouse настройки
        self.ch_host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.ch_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.ch_user = os.getenv('CLICKHOUSE_USER', 'etl_writer')
        self.ch_password = os.getenv('CLICKHOUSE_PASSWORD')
        self.ch_database = os.getenv('CLICKHOUSE_DATABASE', 'zakaz')
        
        # Настройки алертов
        self.tg_bot_token = os.getenv('TG_BOT_TOKEN')
        self.tg_chat_id = os.getenv('TG_CHAT_ID')
        
        # SLO пороги
        self.slo_thresholds = {
            # Свежесть данных (в часах)
            'dm_sales_daily_freshness_today': 2.0,
            'dm_sales_daily_freshness_yesterday': 12.0,
            'dm_vk_ads_daily_freshness_today': 3.0,
            'dm_vk_ads_daily_freshness_yesterday': 15.0,
            
            # Полнота данных (доля от 0 до 1)
            'dm_sales_daily_completeness_today': 0.95,
            'dm_sales_daily_completeness_yesterday': 0.90,
            'dm_vk_ads_daily_completeness_today': 0.90,
            'dm_vk_ads_daily_completeness_yesterday': 0.85,
            
            # Задержка обработки (в часах)
            'dm_sales_daily_latency_today': 4.0,
            'dm_sales_daily_latency_yesterday': 8.0,
            'dm_vk_ads_daily_latency_today': 6.0,
            'dm_vk_ads_daily_latency_yesterday': 12.0,
        }
        
        # Инициализация клиента
        self._init_clickhouse_client()
    
    def _init_clickhouse_client(self):
        """Инициализация ClickHouse клиента."""
        try:
            self.ch_client = clickhouse_connect.get_client(
                host=self.ch_host,
                port=self.ch_port,
                username=self.ch_user,
                password=self.ch_password,
                database=self.ch_database
            )
            logger.info("ClickHouse клиент инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации ClickHouse клиента: {e}")
            raise
    
    def get_latest_sli(self) -> Dict[str, Tuple[float, date]]:
        """Получение последних SLI значений."""
        try:
            query = """
            SELECT 
                table_name,
                metric_name,
                metric_value,
                d
            FROM meta.sli_daily
            WHERE d >= today() - 1
            ORDER BY d DESC, table_name, metric_name
            """
            
            result = self.ch_client.query(query)
            
            sli_values = {}
            for row in result.result_rows:
                table_name, metric_name, metric_value, d = row
                
                # Формируем ключ SLO
                if d == date.today():
                    slo_key = f"{table_name}_{metric_name}_today"
                else:
                    slo_key = f"{table_name}_{metric_name}_yesterday"
                
                sli_values[slo_key] = (metric_value, d)
            
            return sli_values
            
        except Exception as e:
            logger.error(f"Ошибка получения SLI: {e}")
            return {}
    
    def check_slo_violations(self, sli_values: Dict[str, Tuple[float, date]]) -> List[Dict]:
        """Проверка нарушений SLO."""
        violations = []
        
        for slo_key, (sli_value, sli_date) in sli_values.items():
            if slo_key in self.slo_thresholds:
                threshold = self.slo_thresholds[slo_key]
                
                # Для свежести и задержки - меньше лучше
                if 'freshness' in slo_key or 'latency' in slo_key:
                    if sli_value > threshold:
                        violations.append({
                            'slo_key': slo_key,
                            'sli_value': sli_value,
                            'threshold': threshold,
                            'date': sli_date,
                            'severity': 'critical' if sli_value > threshold * 2 else 'warning'
                        })
                
                # Для полноты - больше лучше
                elif 'completeness' in slo_key:
                    if sli_value < threshold:
                        violations.append({
                            'slo_key': slo_key,
                            'sli_value': sli_value,
                            'threshold': threshold,
                            'date': sli_date,
                            'severity': 'critical' if sli_value < threshold * 0.8 else 'warning'
                        })
        
        return violations
    
    def format_violation_message(self, violation: Dict) -> str:
        """Форматирование сообщения о нарушении."""
        slo_key = violation['slo_key']
        sli_value = violation['sli_value']
        threshold = violation['threshold']
        severity = violation['severity']
        violation_date = violation['date']
        
        # Определяем тип метрики
        metric_type = '🕐' if 'freshness' in slo_key else '📊' if 'completeness' in slo_key else '⏱️'
        
        # Формируем сообщение
        message = f"{metric_type} *SLO Violation: {slo_key}*\n"
        message += f"📅 Date: {violation_date}\n"
        message += f"📈 Value: {sli_value:.2f}\n"
        message += f"🎯 Threshold: {threshold:.2f}\n"
        message += f"🚨 Severity: {severity.upper()}\n"
        
        return message
    
    def send_telegram_alert(self, message: str):
        """Отправка алерта в Telegram."""
        if not self.tg_bot_token or not self.tg_chat_id:
            logger.warning("Не настроены TG_BOT_TOKEN или TG_CHAT_ID")
            return
        
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
            data = {
                'chat_id': self.tg_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info("Алерт отправлен в Telegram")
            
        except Exception as e:
            logger.error(f"Ошибка отправки алерта в Telegram: {e}")
    
    def log_alert_to_db(self, violation: Dict):
        """Логирование алерта в базу данных."""
        try:
            alert_sql = """
            INSERT INTO meta.etl_alerts (ts, severity, job, code, message, context_json)
            VALUES (
                now(),
                %(severity)s,
                'slo_guard',
                'SLO_VIOLATION',
                %(message)s,
                %(context)s
            )
            """
            
            self.ch_client.command(
                alert_sql,
                parameters={
                    'severity': violation['severity'],
                    'message': f"SLO violation: {violation['slo_key']}",
                    'context': str(violation)
                }
            )
            
        except Exception as e:
            logger.error(f"Ошибка логирования алерта: {e}")
    
    def check_and_alert(self):
        """Основной метод проверки SLO и отправки алертов."""
        logger.info("Запуск проверки SLO")
        
        try:
            # Шаг 1: Получение последних SLI
            sli_values = self.get_latest_sli()
            
            if not sli_values:
                logger.warning("Нет данных SLI для проверки")
                return
            
            # Шаг 2: Проверка нарушений
            violations = self.check_slo_violations(sli_values)
            
            if not violations:
                logger.info("Нарушений SLO не обнаружено")
                return
            
            # Шаг 3: Отправка алертов
            for violation in violations:
                # Формируем сообщение
                message = self.format_violation_message(violation)
                
                # Отправляем в Telegram
                self.send_telegram_alert(message)
                
                # Логируем в базу
                self.log_alert_to_db(violation)
                
                logger.warning(f"Обнаружено нарушение SLO: {violation['slo_key']} = {violation['sli_value']:.2f}")
            
            logger.info(f"Обработка нарушений SLO завершена. Обнаружено: {len(violations)}")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке SLO: {e}")
            raise
    
    def get_slo_status(self) -> Dict:
        """Получение статуса SLO для отчета."""
        try:
            sli_values = self.get_latest_sli()
            violations = self.check_slo_violations(sli_values)
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'total_checks': len(self.slo_thresholds),
                'violations': len(violations),
                'violations_details': violations,
                'sli_values': sli_values
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса SLO: {e}")
            return {'error': str(e)}


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SLO Guard - мониторинг SLO')
    parser.add_argument(
        '--check',
        action='store_true',
        help='Проверить SLO и отправить алерты'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Показать статус SLO'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Вывести статус в формате JSON'
    )
    
    args = parser.parse_args()
    
    if not args.check and not args.status:
        parser.print_help()
        return 1
    
    try:
        guard = SLOGuard()
        
        if args.check:
            guard.check_and_alert()
        
        if args.status:
            status = guard.get_slo_status()
            
            if args.json:
                import json
                print(json.dumps(status, indent=2, default=str))
            else:
                print(f"SLO Status at {status.get('timestamp')}")
                print(f"Total checks: {status.get('total_checks', 0)}")
                print(f"Violations: {status.get('violations', 0)}")
                
                if status.get('violations', 0) > 0:
                    print("\nViolations:")
                    for violation in status.get('violations_details', []):
                        print(f"  - {violation['slo_key']}: {violation['sli_value']:.2f} (threshold: {violation['threshold']:.2f})")
        
        return 0
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении SLO Guard: {e}")
        return 1


if __name__ == "__main__":
    exit(main())