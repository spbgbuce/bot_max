"""
    Модуль processor.py

    Данный модуль определяет класс Processor, который служит центральным
    компонентом для инициализации и управления всеми воркерами и постером
    в системе мониторинга. Processor создаёт экземпляры воркеров (HTTP,
    Proxmox, ежедневная статистика), запускает их в отдельных потоках,
    инициализирует постер для отправки сообщений и поддерживает бесконечный
    цикл для предотвращения завершения основного потока.

    Классы:
    --------
    - Processor: Основной класс, управляющий запуском всех компонентов системы.

    Ключевые зависимости:
    ----------------------
    - workers.http_worker.HttpWorker: Воркер для мониторинга HTTP-сервисов.
    - workers.proxmox_worker.ProxmoxWorker: Воркер для мониторинга Proxmox.
    - workers.daily_stats_worker.DailyStatsWorker: Воркер для ежедневной статистики.
    - db_manager.DatabaseManager: Менеджер базы данных.
    - posters.poster_factory.PosterFactory: Фабрика для создания постера.
    - threading, queue: Для многопоточности и очереди сообщений.

    Пример использования:
    ----------------------

    # Создание и запуск процессора
    processor = Processor(config)
    processor.start()
"""
from typing import Dict, Any, List
import queue
import threading
from workers.http_worker import HttpWorker
from formatters.http_formatter import HttpProblemFormatter
from workers.proxmox_worker import ProxmoxWorker
from formatters.proxmox_formatter import ProxmoxFormatter
from workers.daily_stats_worker import DailyStatsWorker
from db_manager import DatabaseManager
import time
from posters.poster_factory import PosterFactory
import logging

logger = logging.getLogger(__name__)


class Processor:
    """
    Центральный управляющий компонент системы мониторинга.

    Кратко:
        Processor инициализирует все необходимые зависимости (базу данных,
        очередь сообщений, постер), создаёт список воркеров, запускает их
        в отдельных потоках и поддерживает работу основного потока.

    Args:
        config (Dict[str, Any]): Словарь конфигурации, содержащий все параметры
            для инициализации воркеров и постера.

    Attributes:
        config (Dict[str, Any]): Сохранённая конфигурация.
        db (DatabaseManager): Экземпляр менеджера базы данных.
        result_queue (queue.Queue): Очередь для передачи сообщений от воркеров к постеру.
        poster: Экземпляр постера, созданный через PosterFactory.

    Public methods:
        start() -> None:
            Запускает все компоненты: постер в отдельном потоке, затем каждого воркера
            в отдельном потоке, после чего входит в бесконечный цикл для поддержания
            работы программы.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализирует процессор.

        Args:
            config (Dict[str, Any]): Словарь конфигурации, который должен содержать:
                - "DB_PATH" (опционально, по умолчанию "data/http_stats.db")
                - "POSTER_TYPE": тип постера (например, "bot_max")
                - "TIMESLEEP": интервал проверки для воркеров
                - "HTTP_SITES": список сайтов для HTTP-воркера
                - "PROXMOX_API_TOKEN": токен Proxmox
                - "PROXMOX_BASE_URL": URL API Proxmox
                - "NODES": список узлов Proxmox
                - "STATS_TIME" (опционально): время ежедневной статистики, по умолчанию "08:30"
        """
        self.config = config
        self.db = DatabaseManager(config.get("DB_PATH", "data/http_stats.db"))
        self.result_queue = queue.Queue()
        self.poster = PosterFactory.create_poster(poster_type=config["POSTER_TYPE"], result_queue=self.result_queue, config=config)
        logger.info("Processor initialized")
                    
    def start(self) -> None:
        """
        Запускает все компоненты системы.

        Создаёт постер и запускает его в фоновом потоке, затем создаёт воркеры
        через _create_workers и запускает каждого в отдельном потоке. После
        запуска всех потоков переходит в бесконечный цикл _inf_loop, который
        предотвращает завершение программы.

        Поведение:
            - Постер запускается первым, чтобы начать прослушивание очереди.
            - Каждый воркер запускается в отдельном потоке (daemon=True), поэтому
              они завершатся при завершении основного потока.
            - Основной поток остаётся активным благодаря _inf_loop.
        """
        workers = self._create_workers()
        poster_thread = threading.Thread(target=self.poster.run, daemon=True)
        poster_thread.start()
        logger.debug("Poster thread started")
        for worker in workers:
            worker_thread = threading.Thread(
                target=worker.run,
                args=(self.result_queue,),
                daemon=True
            )
            worker_thread.start()
            logger.debug("Worker thread started")
        self._inf_loop()
            
    def _create_workers(self) -> List:
        """
        Создаёт и возвращает список экземпляров воркеров.

        Использует конфигурацию для создания:
            - HttpWorker: для мониторинга HTTP-сервисов.
            - ProxmoxWorker: для мониторинга виртуальных машин Proxmox.
            - DailyStatsWorker: для формирования ежедневной статистики.

        Returns:
            List: Список объектов воркеров, готовых к запуску.
        """
        workers = [
            HttpWorker(
                http_sites=self.config["HTTP_SITES"],
                formatter=HttpProblemFormatter(),
                time_sleep=self.config["TIMESLEEP"],
                db=self.db 
            ),
            ProxmoxWorker(
                api_token=self.config["PROXMOX_API_TOKEN"],
                proxmox_base_url=self.config["PROXMOX_BASE_URL"],
                nodes=self.config["NODES"],
                formatter=ProxmoxFormatter(),
                time_sleep=self.config["TIMESLEEP"],
                db=self.db 
            ),
            DailyStatsWorker(
                http_sites=self.config["HTTP_SITES"],
                proxmox_token=self.config["PROXMOX_API_TOKEN"],
                proxmox_base_url=self.config["PROXMOX_BASE_URL"],
                nodes=self.config["NODES"],
                result_queue=self.result_queue,
                db=self.db,
                http_interval=self.config["TIMESLEEP"],
                stats_time=self.config.get("STATS_TIME", "08:30")
            )
        ]
        
        return workers
    
    def _inf_loop(self):
        """
        Бесконечный цикл, поддерживающий работу основного потока.

        Выполняет простую задержку в 1 секунду, чтобы не нагружать процессор.
        Необходим для предотвращения завершения программы после запуска всех
        фоновых потоков.
        """
        while True:
            time.sleep(1)
