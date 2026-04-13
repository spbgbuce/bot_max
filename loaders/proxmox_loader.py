"""
    Модуль proxmox_loader.py

    Данный модуль определяет класс, наследуемый от класса BaseLoader()
    Предназначен для отправки get запросов к url proxmox и фильтрации 
    полученных ответов с последующим возвратом этой инфомации

    Классы: 
    ------------
    - ProxmoxLoader: Класс, наследуемый от Абстрактного класса BaseLoader,
     в котором отправляются запросы и возвращается определенная информация из ответов

    Пример использования: 
    ----------------
    1. Создайте подкласс от BaseLoader и реализуйте метод get_data 
    2. При инициализации передайте url
    3. Вызовите get_data(url)

    Пример реализации подкласса: 
        class ProxmoxLoader(BaseLoader):
            def get_data(self, url: str):
                result = requests.get(url)
                # Логика фильтрации полученного результата
                return result
"""
import requests
from typing import Any, Dict
from loaders.http_loader import BaseLoader
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProxmoxLoader(BaseLoader):
    """
    Загрузчик данных из Proxmox по Proxmox VE API

    Кратко:
        Реализация BaseLoader, выполняющая GET-запрос по указанному url proxmox.
        Возвращает структурированную информацию об ответе, включая информацию обо всех
        нодах proxmox, когда был сделан запрос.
    
    Public methods:
        get_data(self, api_token: str, url: str, **kwargs: Any) -> Dict[str, Any]:
            Выполняет get-запрос и возвращает словарь с полями:
                - data (Dict[str, Any]): Информацию обо всех нодах proxmox
                - datetime (datetime): Время выполнения запроса
                - exception (str): Исключение, None если исключения нет
    
    Behavior notes: 
        - При возникновении ошибки, она перехватывается и возвращается в словарь с заполенным полем exception
    
    Ключевые зависимости:
        - requests: для выполнения HTTP-запросов
        - datetime: для фиксации времени запроса
    
    Пример запроса: 
        loader = ProxmoxLoader()
        result = loader.get_data(url="http://api.example.com/data", api_token=IP_TOKEN)
        if result["exception"]:
            return f"Ошибка загрузки: {result['exception']}
        else:
            return result["data"]
    """
    def get_data(self, api_token: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Выполнить GET-запрос к Proxmox API и вернуть структурированный ответ.

        Args:
            api_token (str): Токен авторизации Proxmox (формат "PVEAPIToken=...").
            url (str): URL запроса (например, "https://proxmox/api2/json/nodes").
            **kwargs (Any): Дополнительные параметры (в текущей реализации не используются).

        Returns:
            Dict[str, Any]: Словарь, содержащий:
                - data (Any): данные из ответа API (обычно поле "data" или полный JSON),
                - datetime (datetime): время выполнения запроса,
                - exception (Optional[str]): текст ошибки или None при успехе.
                В случае ошибки поле "data" будет пустым списком [].
        """
        logger.info("ProxmoxLoader: starting request to %s", url)
        try:
            headers = {
                "Authorization": api_token
            }
            response = requests.get(url, headers=headers, verify=False)
            logger.debug("ProxmoxLoader: response status code: %s", response.status_code)
            now = datetime.now()
            response.raise_for_status()
            data = response.json()
            data['datetime'] = now
            data['exception'] = None
            logger.info("ProxmoxLoader: request succeeded, data size: %d items", len(data.get('data', [])))
            return data
        except Exception as e:
            logger.error("ProxmoxLoader: request failed for %s: %s", url, e, exc_info=True)
            return {
                'exception': str(e),
                'datetime': datetime.now(),
                'data': []
            }
