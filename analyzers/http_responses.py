"""
    Модуль http_responses.py

    Данный модуль предоставляет утилиты для работы с HTTP-статусами:
    датакласс для хранения сообщения и описания статуса, а также функцию
    получения структурированной информации о статусе по его коду.
    Предназначен для унификации представления HTTP-ответов в анализаторах
    и других компонентах системы.

    Классы:
    --------
    - HttpStatusResponse: Неизменяемый датакласс, хранящий сообщение
      (краткое наименование) и описание (расширенное пояснение) для
      HTTP-статуса.

    Функции:
    ---------
    - get_status_info(status_code: int, target_key: bool) -> HttpStatusResponse:
        Возвращает объект HttpStatusResponse для заданного кода статуса,
        с учётом флага технического обслуживания (target_key). Если код
        отсутствует в предопределённом словаре, возвращается ответ
        с пометкой "Unknown".

    Ключевые зависимости:
    ----------------------
    - dataclasses: Используется для определения датакласса с опцией frozen.
    - typing: Для аннотаций типов.

    Пример использования:
    ----------------------
    from http_responses import get_status_info

    # Обычный успешный ответ
    response = get_status_info(200, target_key=False)
    print(response.message)      # "OK"
    print(response.description)  # "Запрос выполнен успешно"

    # Сервис временно недоступен
    response = get_status_info(503, target_key=False)
    print(response.message)      # "Service Unavailable"

    # При включённом флаге техобслуживания всегда возвращается специальный ответ
    response = get_status_info(200, target_key=True)
    print(response.message)      # "FAIL"
    print(response.description)  # "Cервисное обслуживание"

    # Неизвестный код
    response = get_status_info(999, target_key=False)
    print(response.message)      # "Unknown"
    print(response.description)  # "Неизвестный код состояния: 999"
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpStatusResponse:
    """
    Неизменяемый объект, представляющий информацию об HTTP-статусе.

    Кратко:
        Используется для хранения структурированных данных о коде состояния
        HTTP: краткого сообщения (например, "OK", "Not Found") и
        дополнительного описания (например, "Запрос выполнен успешно").

    Args:
        message (str): Краткое наименование статуса (например, "OK").
        description (Optional[str]): Расширенное описание статуса.
            Может быть None, если описание не требуется.

    Attributes:
        message (str): Краткое наименование статуса.
        description (Optional[str]): Расширенное описание статуса.

    Note:
        Класс помечен как frozen, поэтому экземпляры неизменяемы после создания.
        Это обеспечивает безопасность при передаче объектов между компонентами.

    Пример:
        response = HttpStatusResponse("OK", "Запрос выполнен успешно")
        print(response.message)      # "OK"
        print(response.description)  # "Запрос выполнен успешно"
    """
    message: str
    description: Optional[str] = None


# Приватный словарь, сопоставляющий коды HTTP с объектами HttpStatusResponse
_HTTP_STATUSES = {
    # ==================== 2xx: Успешно ====================
    200: HttpStatusResponse("OK", "Запрос выполнен успешно"),

    # ==================== 3xx: Перенаправление ====================
    301: HttpStatusResponse("Moved Permanently", "Ресурс перемещен навсегда"),
    302: HttpStatusResponse("Found", "Ресурс временно доступен по другому адресу"),
    304: HttpStatusResponse("Not Modified", "Ресурс не изменился с прошлого запроса"),

    # ==================== 4xx: Ошибки клиента ====================
    400: HttpStatusResponse("Bad Request", "Неверный формат запроса"),
    401: HttpStatusResponse("Unauthorized", "Требуется авторизация"),
    403: HttpStatusResponse("Forbidden", "Доступ запрещен"),
    404: HttpStatusResponse("Not Found", "Ресурс не найден"),
    405: HttpStatusResponse("Method Not Allowed", "Метод не поддерживается"),
    409: HttpStatusResponse("Conflict", "Конфликт с текущим состоянием"),
    410: HttpStatusResponse("Gone", "Ресурс удален"),
    422: HttpStatusResponse("Unprocessable Entity", "Данные не прошли проверку"),
    429: HttpStatusResponse("Too Many Requests", "Слишком много запросов"),

    # ==================== 5xx: Ошибки сервера ====================
    500: HttpStatusResponse("Internal Server Error", "Внутренняя ошибка сервера"),
    501: HttpStatusResponse("Not Implemented", "Функция не реализована"),
    502: HttpStatusResponse("Bad Gateway", "Ошибка на промежуточном сервере"),
    503: HttpStatusResponse("Service Unavailable", "Сервис временно недоступен"),
    504: HttpStatusResponse("Gateway Timeout", "Сервер не дождался ответа"),
}


def get_status_info(status_code: int, target_key: bool) -> HttpStatusResponse:
    """
    Возвращает структурированную информацию об HTTP-статусе.

    Аргументы:
        status_code (int): Код HTTP-статуса (например, 200, 404, 503).
        target_key (bool): Флаг, указывающий на наличие технического обслуживания.
            Если True, всегда возвращается объект с сообщением "FAIL" и
            описанием "Cервисное обслуживание", независимо от кода статуса.
            Это используется для переопределения стандартного ответа, когда
            сайт находится на обслуживании.

    Возвращаемое значение:
        HttpStatusResponse: Объект, содержащий:
            - message (str): Краткое наименование статуса.
            - description (Optional[str]): Описание статуса (может быть None).

    Поведение:
        - Если target_key == True, возвращается специальный ответ "FAIL".
        - Иначе выполняется поиск в словаре _HTTP_STATUSES по status_code.
        - Если код найден, возвращается соответствующий HttpStatusResponse.
        - Если код не найден, возвращается ответ с сообщением "Unknown" и
          описанием "Неизвестный код состояния: <status_code>".

    Пример:
        # Обычный ответ
        response = get_status_info(200, target_key=False)
        print(response.message)      # "OK"
        print(response.description)  # "Запрос выполнен успешно"

        # Флаг техобслуживания переопределяет ответ
        response = get_status_info(200, target_key=True)
        print(response.message)      # "FAIL"
        print(response.description)  # "Cервисное обслуживание"
    """
    if target_key:
        logger.debug("get_status_info: target_key=True, returning FAIL for status %d", status_code)
        return HttpStatusResponse("FAIL", "Cервисное обслуживание")
    
    result = _HTTP_STATUSES.get(
        status_code, 
        HttpStatusResponse("Unknown", f"Неизвестный код состояния: {status_code}")
    )
    if status_code not in _HTTP_STATUSES:
        logger.warning("Unknown HTTP status code: %d", status_code)
    else:
        logger.debug("get_status_info: returning %s for status %d", result.message, status_code)
    
    return result
