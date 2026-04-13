"""
    Модуль http_loader.py

    Данный модуль определяет абстрактный базовый класс BaseLoader() для считывания информации из источников
    Предназначен для унификации интерфейса считывания информации из различных источников.
    Сам по себе не содержит логики валидации - предоставляет каркас для реализации в подклассах.

    HttpLoader() - класс наследуюемый от класса BaseLoader()
    Предназначен для отправки http запросов к url сайтов, 
    и фильтрация полученных ответов с последующим возвратом этой информации

    Классы:
    --------
    - BaseLoader: Абстрактный базовый класс для считывания информации.
      Содержит общий интерфейс (метод get_data)
    - HttpLoader: Класс, наследуемый от Абстрактного класса BaseLoader,
      в котором отправляются http запросы и возвращается определенная информация из ответов 
    
    Пример использования:
    ---------------------
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
from abc import ABC, abstractmethod
import requests
from typing import Any, Dict
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """
    Базовый лоадер файлов.

    Кратко:
        Абстрактный/базовый класс для реализации получения информации из источника.
        
    Args:
        Нет обязательных аргументов конструктора.
    
    Public methods:
        get_data(url: str, **kwargs: Any) -> Dict[str, Any]:
            Абстрактный метод, который должен быть реализован в классе 
            Выполняет получение данных из источника по указанному url
            и возвращает словарь с результатом
    
    Behavior notes:
        - Класс не содержит логики загрузки
        - Реализация get_data в подклассах должна возвращать словарь
        - При невозможности получить данные возвращается словарь
        с полем "exception", содержащим текст ошибки, чтобы не выбрасывать исключение
    """
    @abstractmethod
    def get_data(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Получить данные из источника.

        Args:
            url (str): Адрес источника данных
            **kwargs (Any): Дополнительные параметры запроса
        
        Returns: 
            Dict[str, Any]: Словарь с результатами загрузки.
        """
        pass


class HttpLoader(BaseLoader):
    """
    Загрузчик данных по HTTP

    Кратко: 
        Реализация BaseLoader, выполняющая GET-запрос по указанному URL
        с использованием библиотеки requests. Возвращает структурированную информацию 
        об ответе, включая код статуса, итоговый url, метод, время когда был сделан запрос, 
        возможное исключение и тело запроса через(декодированное в utf-8)

    Purlic methods:
        get_data(url: str, **kwargs: Any) -> Dict[str, Any]:
            Выполняет get-запрос и возвращает словарь с полями:
                - status_code (Optional[int]): HTTP-код ответа или None при ошибке.
                - url (str): Итоговый URL.
                - method (str): Использованный HTTP-метод.
                - date (datetime): Время выполнения запроса.
                - exception (Optional[str]): Текст исключения, если оно возникло,
                  иначе None.
                - html (Optional[str]): Тело ответа, декодированное в UTF-8,
                  или None при ошибке.
    Behavior notes:
        - Таймаут запроса по умолчанию 10 секунд. Можно переопределить через kwargs['timeout']
        - При возникновении ошибки, она перехватывается и возвращается в словарь с заполенным полем exception
        - Тело ответа всегда декодируется как utf-8.
    
    Ключевые зависимости:
        - requests: для выполнения HTTP-запросов
        - datetime: для фиксации времени запроса

    Пример запроса: 
        loader = HttpLoader()
        result = losder.get_data("http://api.example.com/data", timeout=3)
        if result["exception"]:
            print(f"Ошибка загрузки: {result['exception']})
        else:
            print(f"Статус: {result['status_code']}")
            if result["status_code"] == 200:
                print(f"Получено: {result['html']}")
    
    """
    def get_data(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Выполнить HTTP get-запрос и вернуть структурированный ответ

        Args:
            url (str): url запроса.
            **kwargs (Any): Дополнительные параметры:
                - timeout (int): таймаут запроса в секундах (по умолчанию 10)
            
        Returns:
            Dict[str, Any]: словарь с полями:
                - status_code (Optional[int]): код ответа или None
                - url (str): итоговый url
                - method (str): "GET"
                - date (datetime): время запроса
                - exception (Optional[str]): текст ошибки или None
                - html (Optional[str]): тело ответа в utf-8 или None
        """
        
        now = datetime.now()
        timeout = kwargs.get('timeout', 10)
        logger.debug("HttpLoader: requesting %s with timeout %d", url, timeout)
        try:
            response = requests.get(url, timeout=timeout)
            logger.debug("HttpLoader: response status %s for %s", response.status_code, url)
            return {
                "status_code": response.status_code,
                "url": response.url,
                "method": response.request.method,
                "date": now,
                "exception": None,
                "html": response.content.decode('utf-8') 
            }
        except Exception as e:
            logger.error("HttpLoader: error requesting %s: %s", url, e, exc_info=True)
            return {
                "status_code": None,
                "url": url,
                "method": "GET",
                "date": now,
                "exception": str(e),
                "html": None
            }