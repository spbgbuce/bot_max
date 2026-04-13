"""
    Модуль daily_stats_worker.py

    Данный модуль определяет класс DailyStatsWorker – воркер для формирования
    ежедневной сводки о состоянии HTTP-сервисов и виртуальных машин Proxmox.
    Воркер запускается в отдельном потоке, ожидает заданного времени (например,
    08:30), затем собирает статистику из базы данных и текущее состояние
    Proxmox, форматирует сообщение и отправляет его в очередь.

    Классы:
    --------
    - DailyStatsWorker: Воркер для ежедневной сводки, наследующий от Worker.
      Выполняет ожидание до следующего запланированного времени, затем
      получает статистику изменений HTTP и Proxmox, обогащает данными о
      текущем состоянии ВМ, форматирует сообщение через DailyStatsFormatter
      и отправляет в очередь result_queue.

    Ключевые зависимости:
    ----------------------
    - loaders.proxmox_loader.ProxmoxLoader: Для получения текущих данных о ВМ.
    - db_manager.DatabaseManager: Для получения статистики изменений.
    - formatters.daily_stats_formatter.DailyStatsFormatter: Форматтер отчёта.
    - datetime, timedelta: Для работы с временем и ожиданием.

    Пример использования:
    ----------------------
    # Создание экземпляра воркера
    worker = DailyStatsWorker(
        http_sites=http_sites_config,
        proxmox_token="PVEAPIToken=...",
        proxmox_base_url="https://...",
        nodes=["pve"],
        result_queue=queue,
        db=db_manager,
        http_interval=10,
        stats_time="08:30"
    )

    # Запуск в отдельном потоке
    threading.Thread(target=worker.run, daemon=True).start()
"""
import time
import logging
from datetime import datetime, time as dt_time
from typing import List, Dict, Any
from loaders.proxmox_loader import ProxmoxLoader
from db_manager import DatabaseManager
from formatters.daily_stats_formatter import DailyStatsFormatter
from datetime import timedelta
from workers.worker import Worker

logger = logging.getLogger(__name__)


class DailyStatsWorker(Worker):
    """
    Воркер для формирования ежедневной сводки.

    Кратко:
        Ожидает наступления заданного времени суток (например, 08:30), затем
        собирает статистику изменений HTTP-сервисов (количество отказов за сутки,
        время последнего успешного ответа) и Proxmox (количество проблемных
        изменений статуса ВМ), дополняет текущими данными о ВМ (аптайм, статус),
        форматирует итоговое сообщение и помещает его в очередь для отправки.

    Args:
        http_sites (List[Dict[str, Any]]): Список сайтов (не используется напрямую,
            но может быть полезен для расширения).
        proxmox_token (str): Токен для API Proxmox.
        proxmox_base_url (str): Базовый URL API Proxmox.
        nodes (List[str]): Список узлов Proxmox для фильтрации ВМ.
        result_queue (queue.Queue): Очередь для отправки сообщений.
        db (DatabaseManager): Менеджер БД для получения статистики.
        http_interval (int): Интервал проверки HTTP-сервисов (используется
            для форматирования аптайма, но в текущей реализации аптайм
            рассчитывается по времени последнего успешного ответа).
        stats_time (str, optional): Время запуска в формате "HH:MM".
            По умолчанию "08:30".

    Attributes:
        http_sites (List[Dict[str, Any]]): Сохранённый список сайтов.
        proxmox_token (str): Сохранённый токен.
        proxmox_base_url (str): Сохранённый URL.
        nodes (List[str]): Сохранённый список узлов.
        result_queue (queue.Queue): Очередь.
        db (DatabaseManager): Менеджер БД.
        http_interval (int): Сохранённый интервал.
        stats_time (str): Сохранённое время.
        proxmox_loader (ProxmoxLoader): Загрузчик данных Proxmox.
        formatter (DailyStatsFormatter): Форматтер.
        last_run_date (Optional[date]): Дата последнего выполнения.
    """
    def __init__(self, http_sites: List[Dict[str, Any]],
                 proxmox_token: str, proxmox_base_url: str, nodes: List[str],
                 result_queue, db: DatabaseManager, http_interval: int,
                 stats_time: str = "08:30"):
        self.http_sites = http_sites
        self.proxmox_token = proxmox_token
        self.proxmox_base_url = proxmox_base_url
        self.nodes = nodes
        self.result_queue = result_queue
        self.db = db
        self.http_interval = http_interval
        self.stats_time = stats_time
        self.proxmox_loader = ProxmoxLoader()
        self.formatter = DailyStatsFormatter()
        self.last_run_date = None

    def run(self, _=None):
        """
        Основной цикл воркера: ожидание до следующего запланированного времени и выполнение отчёта.

        Args:
            _: Не используется (заглушка для совместимости с абстрактным методом Worker.run).

        Behavior notes:
            - Сначала вычисляется время до следующего запланированного запуска.
              Если текущее время >= target_time, запуск планируется на завтра.
            - После ожидания входит в бесконечный цикл, который каждую минуту проверяет,
              наступило ли целевое время и не было ли уже выполнено сегодня.
            - При выполнении вызывается метод _run_once.
        """
        hour, minute = map(int, self.stats_time.split(':'))
        target_time = dt_time(hour, minute)
        logger.info("Daily stats worker started, target time=%s, interval=%ds", target_time, self.http_interval)
        now = datetime.now()
        target_datetime = datetime.combine(now.date(), target_time)
        if now.time() >= target_time:
            target_datetime += timedelta(days=1)
        sleep_seconds = (target_datetime - now).total_seconds()
        if sleep_seconds > 0:
            logger.info("Waiting %.1f seconds until next scheduled time (%s)", sleep_seconds, target_datetime)
            time.sleep(sleep_seconds)

        while True:
            now = datetime.now()
            if now.time() >= target_time and self.last_run_date != now.date():
                self._run_once()
                self.last_run_date = now.date()
            time.sleep(60)

    def _run_once(self):
        """
        Выполняет сбор статистики и формирование отчёта.

        Behavior notes:
            - Получает статистику HTTP (get_http_stats) и Proxmox (get_proxmox_stats) из БД.
            - Получает текущие данные о ВМ через API Proxmox.
            - Обогащает список ВМ количеством проблемных изменений за сутки.
            - Форматирует сообщение через DailyStatsFormatter и отправляет в очередь.
            - Любые исключения логируются, но не прерывают работу воркера.
        """
        logger.info("Running daily statistics job")
        try:
            http_stats = self.db.get_http_stats(days=1)
            proxmox_stats = self.db.get_proxmox_stats(days=1)
            proxmox_vms = self._get_proxmox_data()                     
            enriched_vms = []
            for vm in proxmox_vms:
                vm_id = vm['vmid']
                _, problem_count = proxmox_stats.get(vm_id, (None, 0))
                enriched_vms.append({
                    'name': vm['name'],
                    'vmid': vm_id,
                    'status': vm['status'],
                    'uptime': vm['uptime'],
                    'problem_changes': problem_count
                })
            message = self.formatter.format(http_stats, enriched_vms, self.http_interval)
            if message:
                self.result_queue.put(message)
                logger.info("Daily statistics message sent")
            else:
                logger.info("No statistics data to send")
        except Exception:
            logger.exception("Failed to run daily stats")

    def _get_proxmox_data(self) -> List[Dict[str, Any]]:
        """
        Получает текущие данные о виртуальных машинах из Proxmox.

        Returns:
            List[Dict[str, Any]]: Список словарей, каждый представляет ВМ.
                Содержит ключи: 'name', 'vmid', 'status', 'uptime', 'node'.
                При ошибке возвращает пустой список.
        """
        raw = self.proxmox_loader.get_data(self.proxmox_token, self.proxmox_base_url)
        if raw.get('exception'):
            logger.error("Proxmox error: %s", raw['exception'])
            return []
        resources = raw.get('data', [])
        vms = []
        for res in resources:
            if res.get('type') in ('qemu', 'lxc') and res.get('node') in self.nodes:
                uptime = res.get('uptime')
                vms.append({
                    'name': res.get('name'),
                    'vmid': res.get('vmid'),
                    'status': res.get('status'),
                    'uptime': uptime if uptime is not None else 0,
                    'node': res.get('node')
                })
        return vms