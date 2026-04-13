"""
    Модуль bot_max_poster.py

    Данный модуль определяет класс BotMaxPoster – реализацию постера,
    который отправляет сообщения в чаты через Max API. Предназначен для
    интеграции с очередью сообщений и отправки уведомлений о статусах
    HTTP-сервисов и Proxmox-виртуальных машин.

    Классы:
    --------
    - BotMaxPoster: Реализация Poster, использующая MaxApiClient для
      отправки сообщений в заданные чаты. Определяет формат сообщения
      на основе содержимого (наличие ключевых слов "url" или "Proxmox")
      и отправляет его всем чатам из конфигурации.

    Ключевые зависимости:
    ----------------------
    - max_api.client.MaxApiClient: Клиент для работы с Max API.
    - queue.Queue: Очередь сообщений для асинхронной обработки.
    - posters.poster.Poster: Абстрактный базовый класс.

    Пример использования:
    ----------------------
    from queue import Queue
    from bot_max_poster import BotMaxPoster

    config = {
        "MAX_BOT_TOKEN": "token123",
        "MAX_BOT_BASE_URL": "https://api.max.example",
        "MAX_CHATS": [123456, 789012]
    }
    queue = Queue()
    poster = BotMaxPoster(queue, config)

    # Запуск в отдельном потоке
    import threading
    threading.Thread(target=poster.run, daemon=True).start()

    # Добавление сообщения в очередь
    queue.put("url https://example.com изменил статус")
"""
from posters.poster import Poster
import queue
from typing import Dict, Any
from max_api.client import MaxApiClient
import logging

logger = logging.getLogger(__name__)


class BotMaxPoster(Poster):
    """
    Постер для отправки сообщений через Max бота.

    Кратко:
        Бесконечно читает сообщения из очереди result_queue, определяет
        тип сообщения по наличию ключевых слов ("url" или "Proxmox"),
        формирует префикс и отправляет сообщение во все чаты, указанные
        в конфигурации (ключ MAX_CHATS). Использует MaxApiClient для
        получения списка чатов и отправки сообщений.

    Args:
        result_queue (queue.Queue): Очередь, из которой постер получает
            сообщения для отправки.
        config (Dict[str, Any]): Конфигурация с параметрами:
            - MAX_BOT_TOKEN (str): Токен для авторизации в Max API.
            - MAX_BOT_BASE_URL (str): Базовый URL Max API.
            - MAX_CHATS (List[int]): Список идентификаторов чатов,
              в которые будут отправляться сообщения.

    Attributes:
        result_queue (queue.Queue): Очередь сообщений.
        config (Dict[str, Any]): Конфигурация.

    Public methods:
        run() -> None:
            Основной цикл постера. Бесконечно ожидает сообщение из очереди,
            при получении формирует текст с префиксом и отправляет его во
            все чаты из конфигурации. При отсутствии сообщений в очереди
            продолжает цикл.

    Behavior notes:
        - Сообщения без префикса получают нейтральный префикс "[Робот]".
        - Если в сообщении есть подстрока "url", используется префикс
          "[HTTP-робот] Изменение статуса url сайта".
        - Если есть подстрока "Proxmox" – префикс "[PM-робот] Изменение
          статуса ВМ в Proxmox".
        - При получении списка чатов фильтруются только те, чей chat_id
          присутствует в config["MAX_CHATS"].
        - Ошибки отправки логируются внутри MaxApiClient; здесь они не
          перехватываются.

    Пример:
        queue = Queue()
        config = {"MAX_BOT_TOKEN": "token", "MAX_BOT_BASE_URL": "https://...", "MAX_CHATS": [123]}
        poster = BotMaxPoster(queue, config)
        queue.put("url example.com – 500 Internal Server Error")
        # в другом потоке: poster.run()
        # сообщение будет отправлено в чат 123 с префиксом "[HTTP-робот] ..."
    """
    def __init__(self, result_queue: queue.Queue, config: Dict[str, Any]):
        """
        Инициализирует постер с очередью и конфигурацией.

        Args:
            result_queue (queue.Queue): Очередь сообщений для отправки.
            config (Dict[str, Any]): Конфигурация (токен, базовый URL, список чатов).
        """
        self.result_queue = result_queue
        self.config = config

    def run(self):
        """
        Запускает бесконечный цикл обработки сообщений из очереди.

        Каждое сообщение обрабатывается:
            1. Извлекается из очереди (блокирующее ожидание).
            2. Выбирается префикс в зависимости от содержимого.
            3. Получается список чатов через MaxApiClient.
            4. Для каждого чата из списка, входящего в config["MAX_CHATS"],
               отправляется сообщение методом post_message.

        Если в очереди нет сообщений, цикл продолжается с небольшой задержкой
        (queue.get блокирует поток, но при queue.Empty не блокируется).
        """
        max_api_client = MaxApiClient(token=self.config["MAX_BOT_TOKEN"], base_url=self.config["MAX_BOT_BASE_URL"])
        while True:
            logger.debug("BotMaxPoster: waiting for message...")
            try:
                raw_message = self.result_queue.get()
                logger.info("BotMaxPoster: received message from queue, sending to chats")
                if "Сводка" in raw_message:
                    message = "[Pобот] Eжедневная сводка\n" + raw_message
                elif "url" in raw_message:
                    message = "[HTTP-робот] Изменение статуса url сайта\n" + raw_message
                elif "Proxmox" in raw_message:
                    message = "[PM-робот] Изменение статуса ВМ в Proxmox\n" + raw_message
                else:
                    message = "[Робот] Изменение статуса\n" + raw_message
                chats = max_api_client.get_chats()
                logger.debug("BotMaxPoster: got %d chats", len(chats))
                for chat in chats:
                    if chat["chat_id"] in self.config["MAX_CHATS"]:
                        logger.info("BotMaxPoster: sending message to chat %s", chat["chat_id"])
                        max_api_client.post_message(message=message, chat_id=chat["chat_id"])

            except queue.Empty:
                continue

