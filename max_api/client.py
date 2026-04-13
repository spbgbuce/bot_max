"""
    Модуль client.py

    Данный модуль предоставляет клиент для взаимодействия с Max API.
    Класс MaxApiClient реализует паттерн Singleton, управляет сессией
    и предоставляет методы для получения информации о чатах, отправки
    сообщений и получения данных о текущем пользователе. Использует
    библиотеку requests для HTTP-запросов.

    Классы:
    --------
    - MaxApiClient: Клиент Max API с поддержкой синглтона.
      Инкапсулирует авторизацию, сессию и основные операции:
        - get_me() – получение информации о текущем пользователе.
        - post_message(message, chat_id) – отправка сообщения в чат.
        - get_chats() – получение списка чатов.

    Ключевые зависимости:
    ----------------------
    - requests: Для выполнения HTTP-запросов.
    - typing: Для аннотаций типов.
    - logging: Для записи событий и ошибок.

    Пример использования:
    ----------------------
    from max_api.client import MaxApiClient

    client = MaxApiClient(token="Bearer token", base_url="https://api.max.example")
    chats = client.get_chats()
    for chat in chats:
        client.post_message("Привет!", chat["chat_id"])
"""
import requests
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class MaxApiClient:
    """
    Клиент Max API.

    Кратко:
        Реализует синглтон для работы с Max API: авторизация через токен,
        управление сессией, методы для получения чатов и отправки сообщений.
        При первом создании экземпляра создаётся сессия requests с заголовком
        Authorization. Последующие вызовы конструктора возвращают тот же
        объект (синглтон).

    Args:
        token (str): Токен авторизации (формат "Bearer <token>").
        base_url (str): Базовый URL API (например, "https://api.max.example").

    Attributes:
        _token (str): Токен авторизации.
        _base_url (str): Базовый URL API.
        _session (requests.Session): Сессия для выполнения запросов.

    Public methods:
        get_me() -> Dict[str, Any]:
            Возвращает информацию о текущем боте. В случае ошибки
            возвращает {"Error": True}.
        post_message(message: str, chat_id: int) -> None:
            Отправляет сообщение в указанный чат.
        get_chats() -> List[Dict[str, Any]]:
            Возвращает список чатов (словари с полями chat_id, name и др.).
            При ошибке возвращает пустой список.

    Behavior notes:
        - Класс реализован как синглтон: повторная инициализация с другими
          параметрами не меняет уже созданный экземпляр.
        - Все методы логируют действия (info, debug, error) с использованием
          модуля logging.
        - Ошибки HTTP-запросов перехватываются, логируются и возвращается
          безопасное значение (пустой список или {"Error": True}).

    Raises:
        Нет явных исключений; ошибки обрабатываются внутри методов.

    Пример использования:
        client = MaxApiClient(token="Bearer abc123", base_url="https://api.max.example")
        chats = client.get_chats()
        for chat in chats:
            client.post_message("Текст", chat["chat_id"])
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            obj = super().__new__(cls)
            cls._instance = obj
        return cls._instance

    def __init__(self, token: str, base_url: str):
        """
        Инициализирует экземпляр клиента (или возвращает существующий).

        При первом вызове создаётся сессия и сохраняются параметры.
        При повторных вызовах конструктор ничего не меняет.

        Args:
            token (str): Токен авторизации.
            base_url (str): Базовый URL API.
        """
        if getattr(self, "_session", None) is not None:
            return

        self._token = token
        self._base_url = base_url
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": self._token,
            "Content-Type": "application/json",
        })
        logger.info("MaxApiClient initialized with base_url: %s", base_url)

    def get_me(self) -> Dict[str, Any]:
        """
        Возвращает информацию о текущем пользователе.

        Returns:
            Dict[str, Any]: Словарь с данными пользователя при успехе,
            или {"Error": True} при ошибке.

        Note:
            В случае ошибки HTTP-запроса (4xx, 5xx, сетевые) логгируется
            ошибка и возвращается словарь с ключом "Error": True.
        """
        logger.debug("MaxApiClient.get_me: calling %s/me", self._base_url)
        try:
            request = self._session.get(f"{self._base_url}/me", timeout=10)
            request.raise_for_status()
            return request.json()
        except requests.exceptions.RequestException as e:
            logger.error("MaxApiClient.get_me: request failed: %s", e, exc_info=True)
            return {"Error": True}

    def post_message(self, message: str, chat_id: int):
        """
        Отправляет сообщение в указанный чат.

        Args:
            message (str): Текст сообщения (поддерживается markdown).
            chat_id (int): Идентификатор чата.

        Note:
            При ошибке отправки (сетевая, HTTP-код не 2xx) логгируется
            ошибка. Исключение не пробрасывается наружу.
        """
        logger.debug("MaxApiClient.post_message: sending to chat %s, message length %d", chat_id, len(message))
        params = {"chat_id": chat_id}
        payload = {
            "text": message,
            "format": "markdown"
        }
        try:

            request = self._session.post(f"{self._base_url}/messages", params=params, json=payload)
            request.raise_for_status()
            logger.info("MaxApiClient.post_message: sent to chat %s, status %d", chat_id, request.status_code)
        except requests.exceptions.RequestException as e:
            logger.error("MaxApiClient.post_message: failed to send to chat %s: %s", chat_id, e, exc_info=True)
            print(f"Ошибка отправки в чат {chat_id}: {e}")

    def get_chats(self) -> List[Dict[str, Any]]:
        """
        Возвращает список чатов.

        Returns:
            List[Dict[str, Any]]: Список словарей с информацией о чатах.
            При ошибке возвращается пустой список.

        Note:
            Ожидается, что ответ API содержит поле "chats" со списком чатов.
            Если ответ не соответствует ожидаемому формату, возвращается
            пустой список.
        """
        logger.debug("MaxApiClient.get_chats: calling %s/chats", self._base_url)
        try:
            request = self._session.get(f"{self._base_url}/chats", timeout=10)
            request.raise_for_status()
            data = request.json()
            chats = data.get("chats", [])
            logger.info("MaxApiClient.get_chats: got %d chats", len(chats))
            return chats
        except requests.exceptions.RequestException as e:
            logger.error("MaxApiClient.get_chats: request failed: %s", e, exc_info=True)
            return []
