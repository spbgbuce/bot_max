"""
    Модуль http_worker.py

    Данный модуль определяет класс HttpWorker - реализацию воркера для мониторинга 
    HTTP-сервисов. Воркер периодически запрашивает URL, анализирует изменения статусов ответов
    (успешно/ошибка/нет ответа), формирует уведомление и сохраняет изменения в базу данных.

    Классы:
    -----------------
    - HttpWorker: Воркер для HTTP, наследуемый от Worker.
      Выполняет цикл: загрузка данных через HttpLoader, анализ через HttpResponseAnalyzer,
      форматирование результата через HttpProblemFormatter, сохранение изменений в БД (если передан объект db)
      и отправка сообщений в очередь result_queue.
      
    Ключевые зависимости:
    ------------------------
    - loaders.http_loader.HttpLoader: Загрузчик HTTP-ответов
    - analyzers.http_response_analyzer.HttpResponseAnalyzer: Анализатор изменений групп статусов.
    - formatters.http_formatter.HttpProblemFormatter: Форматтер сообщений
    - db_manager.DatabaseManager: Менеджер БД для сохранения записей
    - datetime: Для формирования временных меток.

    Пример использования:
    --------------------
    # Создание экземпляра воркера
    worker = HttpWorker(
        http_sites=[{"url": "https://example.com"}],
        formatter=HttpProblemFormatter(),
        time_sleep=10,
        db=db_manager
    )

    # Запуск в отдельном потоке
    threading.Thread(target=worker.run, args=(result_queue,), daemon=True).start()
    """

from loaders.http_loader import HttpLoader
from analyzers.http_response_analyzer import HttpResponseAnalyzer
from workers.worker import Worker
from formatters.http_formatter import HttpProblemFormatter
from typing import List, Dict, Any 
import time
import queue
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class HttpWorker(Worker):
    """
    Воркер для мониторинга HTTP-сервисов.

    Кратко:
        Периодически запрашивает заданные URL, анализирует изменения статусов ответов (успешно/ошибка/нет овтета),
        отправляет уведомления в очередь и сохраняет историю изменений в базу данных.

    Args: 
        http_sites (List[Dict[str, Any]]): Список сайтов для проверки. Каждый элемент - словарь с ключом "url"
        formatter (HttpProblemFormatter): Экземпляр форматттера для формирования сообщений.
        time_sleep (int): Интервал между проверками в секундах.
        db (DatabaseManager, optional): Экземпляр менеджера БД для сохранения записей. 
            Если None, сохранение не выполяется

    Attributes: 
        http_sites (List[Dict[str, Any]]): Сохраненный список сайтов
        http_loader (HttpLoader): Загрузчик HTTP-ответов
        http_analyzer (HttpResponseAnalyzer): Анализатор изменений
        formatter (HttpProblemFormatter): Форматтер
        time_sleep(int): Интервал
        db (DatabaseManager, optional): Менеджер БД.

    Public methods
        run(result_queue: queue.Queue) -> None:
            Основный цикл воркера: загружает данные, анализирует, отправляет результат, сохраняет в БД,
            затем засыпает на time_sleep секунд.
    
    
    """
    def __init__(self, http_sites: List[Dict[str, Any]], formatter: HttpProblemFormatter, time_sleep: int, db=None):
        self.http_sites = http_sites
        self.http_loader = HttpLoader()
        self.http_analyzer = HttpResponseAnalyzer()
        self.formatter = formatter
        self.time_sleep = time_sleep
        self.db = db

    def run(self, result_queue: queue.Queue):
        """
        Основной цикл воркера.

        Args: 
            result_queue (queue.Queue): Очередь, в котором помещаются сформированные сообщения.

        Behavior notes:
            - Загрузка выполняется для каждого URL из http_sites.
            - Если при загрузке возникает исключение, оно логируется, но проверка продолжается.
            - Анализ изменений выполняется на основе текущего состояния и предыдущего (хранится в анализаторе).
            - Для каждого изменения (строки в changes['data']) сохраняется запись в БД через db.save_http_record.
            - Успешность (success) определяется по полю group == "Успешно".
            - Временная метка берётся из ответа (response.get('date')) или текущее время.
            - Сообщение формируется через formatter и отправляется в очередь, если оно не пустое.
        """
        logger.info("HttpWorker: starting check cycle for %d sites", len(self.http_sites))
        while True:
            current_results = {}
            for site in self.http_sites:
                url = site["url"]
                logger.debug("HttpWorker: fetching %s", url)
                raw_result = self.http_loader.get_data(url, timeout=10)
                if raw_result.get('exception'):
                    logger.warning("HttpWorker: error fetching %s: %s", url, raw_result['exception'])
                current_results[url] = raw_result

            changes = self.http_analyzer.analyze(current_results)
            result = self.formatter.format(changes)
            if result != '':
                result_queue.put(result)
            if self.db:
                for change_row in changes.get('data', []):
                    url = change_row[0]
                    curr = current_results.get(url)
                    if not curr:
                        continue
                    success = (curr.get('group') == "Успешно")
                    status_code = curr.get('status_code')
                    status_group = curr.get('group')
                    timestamp = curr.get('date', datetime.now())
                    self.db.save_http_record(
                        url=url,
                        timestamp=timestamp,
                        success=success,
                        status_code=status_code,
                        status_group=status_group
                    )
            time.sleep(self.time_sleep)
