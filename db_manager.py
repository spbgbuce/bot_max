"""
    Модуль db_manager.py 

    Данный модуль предоставляет класс DatabaseManager для работы с базой данных SQLite,
    используемой в системе мониторинга для хранения истории изменений состояния HTTP-сервисов
    и виртуальных машин Promox. Модуль обеспечивает создание таблиц, сохранение записей 
    об изменениях и получение статистики для формирования ежедневных отчетов.

    Классы:
    ---------------
    - DatabaseManager: Менеджер базы данных, инкапсулирующий операции создания таблиц,
      индексов, вставки записей и извлечения статистики.

    Ключевые зависимости:
    -------------------------
    - sqlite3: Встроенная библитека Python для работы с SQLite.
    - logging: Для записи событий и ошибок.
    - datetime: Для работы с временными метками.

    Пример использования: 
    ---------------------
    # Инициализация менеджера
    db = DatabaseManager("data/monitoring.db")

    # Сохранение записи об изменении HTTP-статуса
    db.save_http_record(
        url="https://example.com",
        timestamp="2026-03-30 12:00:00",
        success=True,
        status_code=200,
        status_group="Успешно"
    )

    # Сохранение записи об изменении статуса ВМ в Proxmox
    db.save_proxmox_record(
        vm_id=100,
        vm_name="vm-test",
        timestamp=datetime.now(),
        old_status="running",
        new_status="stopped"
    )

    # Получение статистики по HTTP за последние 1 день
    http_stats = db.get_http_stats(days=1)
    # http_stats имеет вид: {url: (last_success_timestamp, fail_count)}

    # Получение статистики по Proxmox за последние 1 день
    proxmox_stats = db.get_proxmox_stats(days=1)
    # proxmox_stats имеет вид: {vm_id: (last_change_timestamp, problem_changes)}

"""

import sqlite3
import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Менеджер базы данных для хранения истории изменений мониторинга.

    Кратко:
        Создаёт и подготавливает базу данных SQLite (таблицы http_status и proxmox_status,
        индексы), предоставляет методы для сохранения записей об изменениях
        (HTTP-сервисы и Proxmox-ВМ) и методы для извлечения статистики,
        необходимой для ежедневных отчётов.

    Args:
        db_path (str): Путь к файлу базы данных SQLite.

    Attributes:
        db_path (str): Сохранённый путь к базе данных.

    Public methods:
        save_http_record(url, timestamp, success, status_code, status_group) -> None:
            Сохраняет запись об изменении HTTP-статуса в таблицу http_status.
        save_proxmox_record(vm_id, vm_name, timestamp, old_status, new_status) -> None:
            Сохраняет запись об изменении статуса виртуальной машины в таблицу proxmox_status.
        get_http_stats(days) -> Dict[str, Tuple[Optional[str], int]]:
            Возвращает статистику по HTTP-сервисам за последние days дней.
        get_proxmox_stats(days) -> Dict[int, Tuple[Optional[str], int]]:
            Возвращает статистику по Proxmox-ВМ за последние days дней.

    Behavior notes:
        - При инициализации автоматически создаются таблицы и индексы, если их нет.
        - Все операции с БД выполняются в отдельном соединении (context manager),
          что гарантирует корректное закрытие соединения даже при исключениях.
        - При сохранении записей используется таймаут ожидания блокировки (timeout=5.0).
    """
    def __init__(self, db_path: str):
        """
        Инициализирует менеджер базы данных.

        Создаёт директорию для файла БД, если она не существует, и выполняет
        создание таблиц http_status и proxmox_status, а также соответствующих
        индексов.

        Args:
            db_path (str): Путь к файлу базы данных.
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS http_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    success BOOLEAN NOT NULL,
                    status_code INTEGER,
                    status_group TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_url_time ON http_status(url, timestamp)')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxmox_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vm_id INTEGER NOT NULL,
                    vm_name TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_vm_time ON proxmox_status(vm_id, timestamp)')
            
            conn.commit()
        logger.info("Database initialized at %s", self.db_path)

    def save_http_record(self, url: str, timestamp, success: bool, status_code: int = None, status_group: str = None):
        """
        Сохраняет запись об изменении статуса HTTP-сервиса.

        Запись добавляется в таблицу http_status. Если передано значение
        timestamp в виде объекта datetime, оно будет преобразовано в строку
        через вызов str(), что может дать не ISO-формат. Рекомендуется
        передавать строку в формате 'YYYY-MM-DD HH:MM:SS' или использовать
        datetime.isoformat() в вызывающем коде.

        Args:
            url (str): Адрес URL.
            timestamp (str | datetime): Время события (строка в формате SQLite
                или объект datetime).
            success (bool): True, если запрос успешен (статусная группа "Успешно").
            status_code (int, optional): Код HTTP-статуса.
            status_group (str, optional): Группа статуса (например, "Успешно",
                "Ошибка", "Нет ответа").

        Behavior notes:
            - Используется отдельное соединение с таймаутом 5 секунд.
            - При ошибке (например, нарушение ограничений) исключение логируется,
              но не пробрасывается наверх.
        """
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    "INSERT INTO http_status (url, timestamp, success, status_code, status_group) VALUES (?, ?, ?, ?, ?)",
                    (url, timestamp, success, status_code, status_group)
                )
            logger.debug("Saved HTTP record for %s, success=%s, status=%s", url, success, status_code)
        except Exception as e:
            logger.error("Failed to save HTTP record: %s", e)
    
    def save_proxmox_record(self, vm_id: int, vm_name: str, timestamp: datetime, old_status: str, new_status: str):
        """
        Сохраняет запись об изменении статуса виртуальной машины Proxmox.

        Запись добавляется в таблицу proxmox_status. Время сохраняется в формате
        ISO (через timestamp.isoformat()).

        Args:
            vm_id (int): Идентификатор виртуальной машины.
            vm_name (str): Имя виртуальной машины.
            timestamp (datetime): Время события (объект datetime).
            old_status (str): Предыдущий статус (может быть None при первом изменении).
            new_status (str): Новый статус.

        Behavior notes:
            - Используется отдельное соединение с таймаутом 5 секунд.
            - При ошибке (например, нарушение ограничений) исключение логируется,
              но не пробрасывается наверх.
        """
        try:
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                conn.execute(
                    "INSERT INTO proxmox_status (vm_id, vm_name, timestamp, old_status, new_status) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (vm_id, vm_name, timestamp.isoformat(), old_status, new_status)
                )
            logger.debug("Saved Proxmox record for VM %s (%s): %s -> %s", vm_name, vm_id, old_status, new_status)
        except Exception as e:
            logger.error("Failed to save Proxmox record: %s", e)

    def get_http_stats(self, days: int = 1) -> Dict[str, Any]:
        """
        Возвращает статистику по HTTP-сервисам за последние days дней.

        Для каждого URL возвращается:
            - время последнего успешного ответа (success=1) или None, если успешных ответов не было;
            - количество неуспешных ответов (success=0) за указанный период.

        Args:
            days (int, optional): Количество дней для анализа. По умолчанию 1.

        Returns:
            Dict[str, Tuple[Optional[str], int]]: Словарь, где ключ — URL,
                значение — кортеж (last_success_timestamp, fail_count).
                last_success_timestamp — строка в формате SQLite (YYYY-MM-DD HH:MM:SS)
                или None.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                SELECT url, timestamp
                FROM http_status
                WHERE success = 1
                GROUP BY url
                HAVING timestamp = MAX(timestamp)
            ''')
            last_success = {url: ts for url, ts in cur.fetchall()}

            cur = conn.execute('''
            SELECT url, COUNT(*) as fail_count
            FROM http_status
            WHERE success = 0
              AND timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY url
            ''', (days,))
            fail_counts = {url: count for url, count in cur.fetchall()}

            all_urls = set(last_success.keys()) | set(fail_counts.keys())
            result = {}
            for url in all_urls:
                result[url] = (last_success.get(url), fail_counts.get(url, 0))
            return result
    
    def get_proxmox_stats(self, days: int = 1) -> Dict[int, Any]:
        """
        Возвращает статистику по виртуальным машинам Proxmox за последние days дней.

        Для каждой ВМ возвращается:
            - время последнего изменения статуса (любого);
            - количество изменений статуса, которые привели к статусу, отличному от 'running'
              (проблемные изменения) за указанный период.

        Args:
            days (int, optional): Количество дней для анализа. По умолчанию 1.

        Returns:
            Dict[int, Tuple[Optional[str], int]]: Словарь, где ключ — vm_id,
                значение — кортеж (last_change_timestamp, problem_changes).
                last_change_timestamp — строка в формате SQLite (YYYY-MM-DD HH:MM:SS)
                или None.
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('''
                SELECT vm_id, timestamp
                FROM proxmox_status
                WHERE (vm_id, timestamp) IN (
                    SELECT vm_id, MAX(timestamp) FROM proxmox_status GROUP BY vm_id
                )
            ''')
            last_change = {vm_id: ts for vm_id, ts in cur.fetchall()}

            cur = conn.execute('''
                SELECT vm_id, COUNT(*) as cnt
                FROM proxmox_status
                WHERE new_status != 'running'
                AND timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY vm_id
            ''', (days,))
            problem_counts = {vm_id: cnt for vm_id, cnt in cur.fetchall()}

            all_vm_ids = set(last_change.keys()) | set(problem_counts.keys())
            result = {}
            for vm_id in all_vm_ids:
                result[vm_id] = (last_change.get(vm_id), problem_counts.get(vm_id, 0))
            return result