"""
    Модуль http_response_analyzer.py

    Данный модуль определяет класс HttpResponseAnalyzer для анализа HTTP-ответов,
    полученных от различных URL. Предназначен для классификации статусов ответов,
    выявления изменений в группах состояний (успешно/ошибка/нет ответа) и
    формирования отчётов об изменениях. Использует вспомогательную функцию
    get_status_info для получения человекочитаемых сообщений о статусах.

    Классы:
    --------
    - HttpResponseAnalyzer: Анализатор HTTP-ответов, наследующий от Analyzer.
      Выполняет обогащение данных ответов, определяет группу статуса и
      сравнивает текущее состояние с предыдущим для выявления изменений.

    Ключевые зависимости:
    ----------------------
    - analyzers.http_responses.get_status_info: Функция, возвращающая объект
      с полями message и description для заданного кода статуса и флага
      технического обслуживания.
    - copy: Используется для глубокого копирования состояния.
    - .analyzer.Analyzer: Базовый абстрактный класс анализатора.

    Пример использования:
    ----------------------
    1. Получите данные от загрузчика (например, HttpLoader) в формате:
       {
           "https://example.com": {
               "status_code": 200,
               "html": "...",
               "date": datetime.now(),
               ...
           },
           ...
       }
    2. Создайте экземпляр HttpResponseAnalyzer, возможно, с предыдущими данными.
    3. Вызовите analyze(current_data) и получите словарь с изменениями групп статусов.
    4. Обработайте результат (например, для отправки уведомлений).

    Пример кода:
        loader = HttpLoader()
        current_data = {}
        for url in urls:
            current_data[url] = loader.get_data(url)

        analyzer = HttpResponseAnalyzer(previous_data=previous_data)
        changes = analyzer.analyze(current_data)
        for row in changes["data"]:
            print(f"URL {row[0]}: статус изменился с {row[2]} на {row[3]}")
"""
from typing import Any, Dict
from analyzers.http_responses import get_status_info
import copy
from .analyzer import Analyzer
import logging


logger = logging.getLogger(__name__)


class HttpResponseAnalyzer(Analyzer):
    """
    Анализатор HTTP-ответов.

    Кратко:
        Класс для обработки и сравнения HTTP-ответов, полученных от множества URL.
        Обогащает входные данные дополнительными полями (message, description, group),
        затем сравнивает текущее состояние с предыдущим, выявляя URL, у которых
        изменилась группа статуса (успешно, ошибка, нет ответа). Результат возвращается
        в виде структурированного словаря с заголовками и строками изменений.

    Args:
        previous_data (Optional[Dict[str, Any]]): Словарь с предыдущими данными
            (результат предыдущего анализа, обогащённый полями group и др.).
            Если None, при первом вызове analyze вернётся полный список всех URL
            без сравнения изменений.

    Attributes:
        previous_data (Optional[Dict[str, Any]]): Сохранённые данные предыдущего анализа.
            Используется для сравнения изменений.

    Public methods:
        analyze(current_data: Dict[str, Any]) -> Dict[str, Any]:
            Обрабатывает входные данные, добавляет поля 'message', 'description', 'group',
            затем сравнивает с предыдущим состоянием и возвращает словарь с изменениями.

        compare_statuses(current_data: Dict[str, Any]) -> Dict[str, Any]:
            Сравнивает группы статусов в текущих и предыдущих данных.
            Возвращает словарь с заголовками и строками изменений (только URL,
            у которых группа изменилась). Если предыдущих данных нет, возвращает
            полный список всех URL с базовой информацией.

        get_status_group(status_code: int, target_key: bool = False) -> str:
            Определяет группу статуса (категорию) на основе кода статуса и флага
            обнаружения "Техническое обслуживание" в HTML.

        find_target_html(html: str) -> bool:
            Проверяет, содержит ли HTML-код строку "Техническое обслуживание".

    Behavior notes:
        - Метод analyze модифицирует входной словарь current_data, добавляя
          поля 'message', 'description', 'group'. Это побочный эффект, поэтому
          входные данные не должны использоваться повторно без копирования.
        - После выполнения analyze текущее состояние сохраняется в previous_data
          (глубокая копия) для последующих вызовов.
        - Группы статусов:
            - "Нет ответа" — если status_code is None.
            - "Ошибка" — если target_key == True (обнаружено техническое обслуживание)
              или код статуса в диапазоне 400–599.
            - "Успешно" — если код статуса в диапазоне 100–399 и нет признака техобслуживания.
            - "Неизвестно" — для прочих случаев.
        - В compare_statuses сравнение идёт по полю 'group'

    Raises:
        Нет явных исключений. Ошибки внутри get_status_info могут пробрасываться,
        если функция их генерирует.

    Ключевые зависимости:
        - analyzers.http_responses.get_status_info: возвращает объект с атрибутами
          message и description.
        - copy.deepcopy: для сохранения состояния.
        - .analyzer.Analyzer: базовый класс.

    Пример использования:
        # Предположим, есть предыдущие данные
        prev_data = {
            "https://site1.com": {"group": "Успешно", "status_code": 200, ...},
            "https://site2.com": {"group": "Ошибка", "status_code": 500, ...},
        }
        analyzer = HttpResponseAnalyzer(previous_data=prev_data)

        # Новые данные
        current_data = {
            "https://site1.com": {"status_code": 200, "html": "...", "date": ...},
            "https://site2.com": {"status_code": 200, "html": "...", "date": ...},
            "https://site3.com": {"status_code": None, "html": None, "date": ...},
        }

        changes = analyzer.analyze(current_data)
        # changes["data"] будет содержать строки для site2 (группа изменилась с Ошибка на Успешно)
        # и для site3 (группа Нет ответа, ранее отсутствовал -> изменение)
        for row in changes["data"]:
            print(row[0], row[2], "->", row[3])
    """
    def __init__(self, previous_data: Dict[str, Any] = None):
        """
        Инициализирует анализатор HTTP-ответов.

        Args:
            previous_data (Optional[Dict[str, Any]]): Предыдущие данные анализа.
                Ожидается, что это словарь с ключами-URL, значениями — словарями,
                содержащими как минимум поле 'group'.
        """
        logger.info("HttpResponseAnalyzer initialized, previous_data: %s", "present" if previous_data else "None")
        self.previous_data = previous_data

    def analyze(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет анализ HTTP-ответов.

        Обогащает каждый ответ в current_data полями 'message', 'description' и 'group',
        затем сравнивает текущее состояние с предыдущим, сохраняет текущее состояние
        и возвращает словарь с изменениями.

        Args:
            current_data (Dict[str, Any]): Словарь, где ключи — URL,
                значения — словари с полями (обязательно: 'status_code', 'html',
                'date' и другие, переданные загрузчиком). Метод будет изменять
                этот словарь, добавляя поля.

        Returns:
            Dict[str, Any]: Словарь, содержащий:
                - 'headers' (List[str]): Заголовки таблицы изменений.
                - 'data' (List[List]): Список строк с изменениями. Каждая строка
                  содержит: [URL, время проверки, прошлый статус, текущий статус,
                  сообщение, описание]. В случае, если предыдущих данных нет,
                  возвращаются все URL, а прошлый статус помечается как "—".
        """
        logger.info("HttpResponseAnalyzer: starting analysis of %d URLs", len(current_data))
        for url, response in current_data.items():
            status_code = response.get("status_code")
            target_key: bool = self.find_target_html(response.get("html"))

            if status_code is None:
                logger.debug("URL %s: no status code, marking as failed", url)
                response["message"] = "No status code"
                response["description"] = "Request failed or no response"
            else:
                logger.debug("URL %s: status %d, target_key=%s, group=%s", url, status_code, target_key, self.get_status_group(status_code, target_key))
                http_response = get_status_info(status_code, target_key)
                response["message"] = http_response.message
                response["description"] = http_response.description
            response["group"] = self.get_status_group(status_code, target_key)

        changes = self.compare_statuses(current_data)
        logger.info("HttpResponseAnalyzer: analysis completed, found %d changes", len(changes.get('data', [])))
        self.previous_data = copy.deepcopy(current_data)
        
        return changes

    def compare_statuses(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сравнивает группы статусов текущих и предыдущих данных.

        Args:
            current_data (Dict[str, Any]): Текущие данные, обогащённые полем 'group'
                (и другими полями, необходимыми для отображения).

        Returns:
            Dict[str, Any]: Словарь с ключами:
                - 'headers': фиксированные заголовки.
                - 'data': список строк изменений. Каждая строка содержит:
                    [url, время проверки, прошлый статус (код), текущий статус (код),
                     сообщение (message), описание (description)].
                Если предыдущих данных нет, возвращаются все URL, а прошлый статус
                помечается "—".
        """
        data = []
        if self.previous_data is None:
            logger.info("No previous data, returning all URLs as initial snapshot")
            for url, response in current_data.items():
                data.append([
                    url,
                    response.get("date", ""),
                    "— (нет данных)",
                    response.get("status_code"),
                    response.get("message", ""),
                    response.get("description", "")
                ])
            return {
                'headers': ['Url сайта', 'Время проверки', 'Прошлый статус', 'Текущий статус', 'Сообщение', 'Описание'],
                'data': data
            }
        all_urls = set(self.previous_data.keys()) | set(current_data.keys())
        for url in sorted(all_urls):
            prev = self.previous_data.get(url)
            curr = current_data.get(url)

            prev_group = prev.get("group") if prev else None
            curr_group = curr.get("group") if curr else None
            logger.debug("URL %s: group changed from %s to %s", url, prev_group, curr_group)

            if prev_group != curr_group:
                prev_status = prev.get("status_code") if prev else None
                curr_status = curr.get("status_code") if curr else None
                data.append([url, curr.get("date"), prev_status, curr_status, curr.get("message") + '/' + prev.get("message"), curr.get("description") + "/" + prev.get("description")])

        return {
            'headers': ['Url сайта', 'Время проверки', 'Прошлый статус', 'Текущий статус', 'Сообщение', 'Описание'],
            'data': data
        }

    def get_status_group(self, status_code: int, target_key: bool = False) -> str:
        """
        Определяет группу статуса на основе кода HTTP и флага технического обслуживания.

        Группы:
            - "Нет ответа" — если status_code is None.
            - "Ошибка" — если target_key == True (обнаружено техобслуживание) или
              код статуса в диапазоне 400–599.
            - "Успешно" — если код статуса в диапазоне 100–399 и target_key == False.
            - "Неизвестно" — для всех остальных случаев.

        Args:
            status_code (int): Код HTTP-статуса.
            target_key (bool): Признак наличия в HTML текста "Техническое обслуживание".

        Returns:
            str: Название группы.
        """
        if status_code is None:
            return "Нет ответа"
        elif target_key:
            return "Ошибка"
        elif 100 <= status_code < 400:
            return "Успешно"
        elif 400 <= status_code < 600:
            return "Ошибка"
        return "Неизвестно"

    def find_target_html(self, html: str) -> bool:
        """
        Проверяет, содержится ли в HTML-коде строка "Техническое обслуживание".

        Args:
            html (str): HTML-код страницы (может быть None).

        Returns:
            bool: True, если строка найдена, иначе False.
        """
        
        if html and "Техническое обслуживание" in html:
            logger.warning("Found 'Техническое обслуживание' in HTML")
            return True
        else:
            return False
