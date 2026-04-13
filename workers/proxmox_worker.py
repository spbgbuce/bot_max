"""
    Модуль proxmox_worker.py

    Данный модуль определяет класс ProxmoxWorker – реализацию воркера для
    мониторинга виртуальных машин (ВМ) в Proxmox VE. Воркер периодически
    получает данные о ресурсах кластера, анализирует изменения статусов ВМ,
    формирует уведомления и сохраняет изменения в базу данных.

    Классы:
    --------
    - ProxmoxWorker: Воркер для Proxmox, наследующий от Worker.
      Выполняет цикл: загрузка данных через ProxmoxLoader, анализ через
      ProxmoxAnalyzer, форматирование результата через ProxmoxFormatter,
      сохранение изменений в БД (если передан объект db) и отправка
      сообщений в очередь result_queue.

    Ключевые зависимости:
    ----------------------
    - loaders.proxmox_loader.ProxmoxLoader: Загрузчик данных из API Proxmox.
    - analyzers.proxmox_analyzer.ProxmoxAnalyzer: Анализатор изменений состояния ВМ.
    - formatters.proxmox_formatter.ProxmoxFormatter: Форматтер сообщений об изменениях.
    - db_manager.DatabaseManager: Менеджер БД (опционально) для сохранения записей.
    - datetime: Для формирования временных меток.

    Пример использования:
    ----------------------
    # Создание экземпляра воркера
    worker = ProxmoxWorker(
        api_token="PVEAPIToken=user@pve!token=xxx",
        proxmox_base_url="https://192.168.1.90:8006/api2/json",
        nodes=["pve"],
        formatter=ProxmoxFormatter(),
        time_sleep=10,
        db=db_manager
    )

    # Запуск в отдельном потоке
    threading.Thread(target=worker.run, args=(result_queue,), daemon=True).start()
"""

from typing import Any, List
from loaders.proxmox_loader import ProxmoxLoader
from analyzers.proxmox_analyzer import ProxmoxAnalyzer
from workers.worker import Worker
from formatters.proxmox_formatter import ProxmoxFormatter
import queue
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ProxmoxWorker(Worker):
    """
    Воркер для мониторинга виртуальных машин Proxmox.

    Кратко:
        Периодически запрашивает данные о ресурсах кластера Proxmox,
        анализирует изменения статусов ВМ, отправляет уведомления в очередь
        и сохраняет историю изменений в базу данных.

    Args:
        api_token (str): Токен для аутентификации в Proxmox API.
        proxmox_base_url (str): Базовый URL API Proxmox.
        nodes (List[str]): Список имён узлов Proxmox, за которыми нужно следить.
        formatter (ProxmoxFormatter): Экземпляр форматтера для формирования сообщений.
        time_sleep (int, optional): Интервал между проверками в секундах. По умолчанию 10.
        db (DatabaseManager, optional): Экземпляр менеджера БД для сохранения записей.
            Если None, сохранение не выполняется.
        **kwargs: Дополнительные аргументы (не используются).

    Attributes:
        api_token (str): Сохранённый токен.
        proxmox_base_url (str): Сохранённый URL.
        nodes (List[str]): Сохранённый список узлов.
        proxmox_loader (ProxmoxLoader): Загрузчик данных.
        proxmox_analyzer (ProxmoxAnalyzer): Анализатор изменений.
        formatter (ProxmoxFormatter): Форматтер.
        time_sleep (int): Интервал.
        db (DatabaseManager, optional): Менеджер БД.
    """
    def __init__(
            self,
            api_token: str,
            proxmox_base_url: str,
            nodes: List[str],
            formatter: ProxmoxFormatter,
            time_sleep: int = 10,
            db=None,
            **kwargs: Any):

        self.api_token = api_token
        self.proxmox_base_url = proxmox_base_url
        self.nodes = nodes
        self.proxmox_loader = ProxmoxLoader()
        self.proxmox_analyzer = ProxmoxAnalyzer(nodes=self.nodes)
        self.formatter = formatter
        self.time_sleep = time_sleep
        self.db = db

    def run(self, result_queue: queue.Queue):
        """
        Основной цикл воркера.

        Args:
            result_queue (queue.Queue): Очередь, в которую помещаются сформированные сообщения.

        Behavior notes:
            - При ошибке загрузки (raw_result.get('exception')) отправляется сообщение об ошибке,
              без анализа.
            - Анализ изменений выполняется только при успешной загрузке данных.
            - Если передан db, для каждого изменения статуса ВМ сохраняется запись в таблицу
              proxmosis_status. При первом запуске (старое состояние отсутствует) old_status = None.
            - Сообщение формируется через formatter и отправляется в очередь, если оно не пустое.
        """
        logger.info("ProxmoxWorker: starting check cycle")
        while True:
            raw_result = self.proxmox_loader.get_data(self.api_token, url=self.proxmox_base_url)

            if raw_result.get('exception'):
                result = f"Ошибка при проверке Proxmox: {raw_result['exception']}"
                logger.error("ProxmoxWorker: error during request: %s", raw_result['exception'])
            else:
                logger.debug("ProxmoxWorker: got %d resources", len(raw_result.get('data', [])))
                changes = self.proxmox_analyzer.analyze(raw_result)
                if self.db:
                    for change in changes.get('data', []):
                        if len(change) == 3:
                            vm_name, vm_id, new_status = change
                            old_status = None
                        elif len(change) >= 4:
                            vm_name, vm_id, old_status, new_status = change[:4]
                        else:
                            logger.warning("Unexpected change format: %s", change)
                            continue

                        self.db.save_proxmox_record(
                            vm_id=vm_id,
                            vm_name=vm_name,
                            timestamp=datetime.now(),
                            old_status=old_status,
                            new_status=new_status
                        )
                result = self.formatter.format(changes)   
            if result != '':
                logger.info("ProxmoxWorker: detected %d changes, sending to queue", len(changes.get('data', [])))
                result_queue.put(result)
            time.sleep(self.time_sleep)
