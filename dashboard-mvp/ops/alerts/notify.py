"""
Система уведомлений об ошибках и событиях интеграций.
Отправляет email уведомления при ошибках в загрузчиках.
"""

import os
import sys
import argparse
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from typing import Dict, List, Any, Optional

# Добавляем корень проекта в путь для импорта общих модулей
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from integrations.common import (
    ClickHouseClient, get_client, 
    now_msk, setup_integrations_logger
)

# Настройка логгера
logger = setup_integrations_logger('notify')

class EmailNotifier:
    """Класс для отправки email уведомлений."""
    
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, 
                 smtp_password: str, use_tls: bool = True):
        """
        Инициализация email нотификатора.
        
        Args:
            smtp_host: SMTP сервер
            smtp_port: SMTP порт
            smtp_user: пользователь SMTP
            smtp_password: пароль SMTP
            use_tls: использовать TLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_tls = use_tls
    
    def send_email(self, to_emails: List[str], subject: str, 
                  body: str, html_body: str = None) -> bool:
        """
        Отправка email.
        
        Args:
            to_emails: список адресатов
            subject: тема письма
            body: текст письма
            html_body: HTML версия письма (опционально)
            
        Returns:
            True если отправка успешна
        """
        try:
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_user
            msg['To'] = ', '.join(to_emails)
            
            # Добавляем текстовую версию
            text_part = MimeText(body, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Добавляем HTML версию если есть
            if html_body:
                html_part = MimeText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Отправка письма
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email отправлен на {', '.join(to_emails)}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False

class AlertManager:
    """Менеджер алертов."""
    
    def __init__(self, ch_client: ClickHouseClient, notifier: EmailNotifier):
        """
        Инициализация менеджера алертов.
        
        Args:
            ch_client: клиент ClickHouse
            notifier: email нотификатор
        """
        self.ch_client = ch_client
        self.notifier = notifier
    
    def check_failed_jobs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Проверка неудачных запусков задач.
        
        Args:
            hours: период проверки в часах
            
        Returns:
            Список неудачных запусков
        """
        since = now_msk() - timedelta(hours=hours)
        
        query = """
        SELECT 
            job,
            started_at,
            finished_at,
            message,
            rows_processed
        FROM zakaz.meta_job_runs
        WHERE status = 'error' 
          AND started_at >= %(since)s
        ORDER BY started_at DESC
        """
        
        try:
            result = self.ch_client.execute(query, {'since': since})
            return result.first_row
        except Exception as e:
            logger.error(f"Ошибка при проверке неудачных запусков: {e}")
            return []
    
    def check_data_freshness(self) -> List[Dict[str, Any]]:
        """
        Проверка свежести данных.
        
        Returns:
            Список источников с устаревшими данными
        """
        query = """
        SELECT 
            source,
            latest_date,
            days_behind,
            total_rows
        FROM zakaz.v_data_freshness
        WHERE days_behind > 2
        ORDER BY days_behind DESC
        """
        
        try:
            result = self.ch_client.execute(query)
            return result.first_row
        except Exception as e:
            logger.error(f"Ошибка при проверке свежести данных: {e}")
            return []
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Комплексная проверка здоровья системы.
        
        Returns:
            Результаты проверки
        """
        try:
            # Выполняем smoke-проверки
            smoke_query = """
            SELECT 
                check_name,
                status,
                message
            FROM (
                SELECT 'system_health' as check_name,
                       CASE 
                         WHEN error_count = 0 THEN 'OK'
                         WHEN error_count <= 2 THEN 'WARNING'
                         ELSE 'ERROR'
                       END as status,
                       concat('System health: ', error_count, ' errors, ', warning_count, ' warnings') as message
                FROM (
                    SELECT 
                        sumIf(status = 'ERROR', 1, 0) as error_count,
                        sumIf(status = 'WARNING', 1, 0) as warning_count
                    FROM (
                        SELECT 'qtickets_sales_freshness' as check_name,
                               'OK' as status
                        FROM zakaz.v_sales_latest
                        WHERE event_date >= today() - 2
                        LIMIT 1
                        UNION ALL
                        SELECT 'qtickets_sales_freshness' as check_name,
                               'ERROR' as status
                        UNION ALL
                        SELECT 'vk_ads_freshness' as check_name,
                               'OK' as status
                        FROM zakaz.fact_vk_ads_daily
                        WHERE stat_date >= today() - 2
                        LIMIT 1
                        UNION ALL
                        SELECT 'vk_ads_freshness' as check_name,
                               'ERROR' as status
                        UNION ALL
                        SELECT 'direct_freshness' as check_name,
                               'OK' as status
                        FROM zakaz.fact_direct_daily
                        WHERE stat_date >= today() - 2
                        LIMIT 1
                        UNION ALL
                        SELECT 'direct_freshness' as check_name,
                               'ERROR' as status
                    ) checks
                ) summary
            )
            """
            
            result = self.ch_client.execute(smoke_query)
            rows = result.first_row
            
            if rows:
                return rows[0]
            else:
                return {
                    'check_name': 'system_health',
                    'status': 'ERROR',
                    'message': 'Не удалось выполнить проверку здоровья системы'
                }
                
        except Exception as e:
            logger.error(f"Ошибка при проверке здоровья системы: {e}")
            return {
                'check_name': 'system_health',
                'status': 'ERROR',
                'message': f'Ошибка проверки: {str(e)}'
            }
    
    def create_alert(self, alert_type: str, title: str, message: str, 
                    details: Dict[str, Any] = None) -> bool:
        """
        Создание алерта в ClickHouse.
        
        Args:
            alert_type: тип алерта (error, warning, info)
            title: заголовок
            message: сообщение
            details: детали
            
        Returns:
            True если алерт создан
        """
        try:
            alert_data = {
                'job': 'alert_manager',
                'alert_type': alert_type,
                'title': title,
                'message': message,
                'details': json.dumps(details or {}),
            }
            
            self.ch_client.insert('zakaz.alerts', [alert_data])
            logger.info(f"Создан алерт: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при создании алерта: {e}")
            return False
    
    def send_error_notification(self, failed_jobs: List[Dict[str, Any]]) -> bool:
        """
        Отправка уведомления об ошибках.
        
        Args:
            failed_jobs: список неудачных запусков
            
        Returns:
            True если уведомление отправлено
        """
        if not failed_jobs:
            return True
        
        # Формируем тему и тело письма
        subject = f"🚨 Ошибки в загрузчиках данных ({len(failed_jobs)})"
        
        # Текстовая версия
        body_lines = [
            "Обнаружены ошибки при выполнении загрузчиков данных:",
            "",
        ]
        
        for job in failed_jobs:
            body_lines.extend([
                f"Задача: {job['job']}",
                f"Время запуска: {job['started_at']}",
                f"Ошибка: {job['message']}",
                f"Обработано строк: {job['rows_processed']}",
                "---"
            ])
        
        body_lines.extend([
            "",
            "Проверьте логи для получения дополнительной информации:",
            "journalctl -u <service_name>.service -n 100",
            "",
            "Или воспользуйтесь скриптом управления:",
            "./ops/systemd/manage_timers.sh logs <job_name>"
        ])
        
        body = "\n".join(body_lines)
        
        # HTML версия
        html_body = f"""
        <html>
        <body>
            <h2>🚨 Ошибки в загрузчиках данных ({len(failed_jobs)})</h2>
            
            <table border="1" cellpadding="5" cellspacing="0">
                <tr>
                    <th>Задача</th>
                    <th>Время запуска</th>
                    <th>Ошибка</th>
                    <th>Обработано строк</th>
                </tr>
        """
        
        for job in failed_jobs:
            html_body += f"""
                <tr>
                    <td>{job['job']}</td>
                    <td>{job['started_at']}</td>
                    <td>{job['message']}</td>
                    <td>{job['rows_processed']}</td>
                </tr>
            """
        
        html_body += """
            </table>
            
            <h3>Действия:</h3>
            <ul>
                <li>Проверьте логи: <code>journalctl -u <service_name>.service -n 100</code></li>
                <li>Используйте скрипт управления: <code>./ops/systemd/manage_timers.sh logs <job_name></code></li>
                <li>Перезапустите задачу: <code>sudo ./ops/systemd/manage_timers.sh restart <job_name></code></li>
            </ul>
        </body>
        </html>
        """
        
        # Получаем адресатов из переменных окружения
        to_emails = os.getenv('ALERT_EMAIL_TO', 'ads-irsshow@yandex.ru').split(',')
        
        # Отправляем уведомление
        return self.notifier.send_email(to_emails, subject, body, html_body)
    
    def send_freshness_notification(self, stale_data: List[Dict[str, Any]]) -> bool:
        """
        Отправка уведомления об устаревших данных.
        
        Args:
            stale_data: список источников с устаревшими данными
            
        Returns:
            True если уведомление отправлено
        """
        if not stale_data:
            return True
        
        # Формируем тему и тело письма
        subject = f"⚠️ Устаревшие данные ({len(stale_data)} источников)"
        
        # Текстовая версия
        body_lines = [
            "Обнаружены источники с устаревшими данными:",
            "",
        ]
        
        for source in stale_data:
            body_lines.extend([
                f"Источник: {source['source']}",
                f"Последние данные: {source['latest_date']}",
                f"Отставание: {source['days_behind']} дней",
                f"Всего строк: {source['total_rows']}",
                "---"
            ])
        
        body_lines.extend([
            "",
            "Проверьте состояние загрузчиков:",
            "./ops/systemd/manage_timers.sh status"
        ])
        
        body = "\n".join(body_lines)
        
        # HTML версия
        html_body = f"""
        <html>
        <body>
            <h2>⚠️ Устаревшие данные ({len(stale_data)} источников)</h2>
            
            <table border="1" cellpadding="5" cellspacing="0">
                <tr>
                    <th>Источник</th>
                    <th>Последние данные</th>
                    <th>Отставание</th>
                    <th>Всего строк</th>
                </tr>
        """
        
        for source in stale_data:
            html_body += f"""
                <tr>
                    <td>{source['source']}</td>
                    <td>{source['latest_date']}</td>
                    <td>{source['days_behind']} дней</td>
                    <td>{source['total_rows']}</td>
                </tr>
            """
        
        html_body += """
            </table>
            
            <h3>Действия:</h3>
            <ul>
                <li>Проверьте состояние загрузчиков: <code>./ops/systemd/manage_timers.sh status</code></li>
                <li>Проверьте логи проблемных загрузчиков</li>
                <li>При необходимости перезапустите загрузчики</li>
            </ul>
        </body>
        </html>
        """
        
        # Получаем адресатов из переменных окружения
        to_emails = os.getenv('ALERT_EMAIL_TO', 'ads-irsshow@yandex.ru').split(',')
        
        # Отправляем уведомление
        return self.notifier.send_email(to_emails, subject, body, html_body)

def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description='Система уведомлений')
    parser.add_argument('--check-errors', action='store_true', help='Проверить ошибки')
    parser.add_argument('--check-freshness', action='store_true', help='Проверить свежесть данных')
    parser.add_argument('--check-health', action='store_true', help='Проверить здоровье системы')
    parser.add_argument('--hours', type=int, default=24, help='Период проверки в часах')
    parser.add_argument('--env', type=str, default='secrets/.env.ch', 
                       help='Путь к файлу с переменными окружения')
    
    args = parser.parse_args()
    
    # Загрузка переменных окружения
    from dotenv import load_dotenv
    load_dotenv(args.env)
    
    # Проверка обязательных параметров
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = os.getenv('SMTP_PORT', '587')
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if not all([smtp_host, smtp_user, smtp_password]):
        logger.error("Не указаны обязательные параметры SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
        sys.exit(1)
    
    try:
        # Инициализация клиентов
        ch_client = get_client(args.env)
        
        notifier = EmailNotifier(
            smtp_host=smtp_host,
            smtp_port=int(smtp_port),
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        )
        
        alert_manager = AlertManager(ch_client, notifier)
        
        # Проверка ошибок
        if args.check_errors or (not args.check_freshness and not args.check_health):
            logger.info("Проверка ошибок...")
            failed_jobs = alert_manager.check_failed_jobs(args.hours)
            
            if failed_jobs:
                logger.warning(f"Обнаружено {len(failed_jobs)} неудачных запусков")
                alert_manager.send_error_notification(failed_jobs)
                
                # Создаем алерты в БД
                for job in failed_jobs:
                    alert_manager.create_alert(
                        'error',
                        f"Ошибка в {job['job']}",
                        job['message'],
                        job
                    )
            else:
                logger.info("Ошибки не обнаружены")
        
        # Проверка свежести данных
        if args.check_freshness or (not args.check_errors and not args.check_health):
            logger.info("Проверка свежести данных...")
            stale_data = alert_manager.check_data_freshness()
            
            if stale_data:
                logger.warning(f"Обнаружено {len(stale_data)} источников с устаревшими данными")
                alert_manager.send_freshness_notification(stale_data)
                
                # Создаем алерты в БД
                for source in stale_data:
                    alert_manager.create_alert(
                        'warning',
                        f"Устаревшие данные в {source['source']}",
                        f"Отставание: {source['days_behind']} дней",
                        source
                    )
            else:
                logger.info("Устаревшие данные не обнаружены")
        
        # Проверка здоровья системы
        if args.check_health:
            logger.info("Проверка здоровья системы...")
            health = alert_manager.check_system_health()
            
            if health['status'] != 'OK':
                logger.warning(f"Проблемы со здоровьем системы: {health['message']}")
                alert_manager.create_alert(
                    health['status'].lower(),
                    "Проблемы со здоровьем системы",
                    health['message'],
                    health
                )
            else:
                logger.info("Система работает нормально")
        
        logger.info("Проверка завершена")
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении проверки: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()