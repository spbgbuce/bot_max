"""
    Модуль http_problem_formatter.py

    Данный модуль определяет класс HttpProblemFormatter, который форматирует
    данные об изменениях статусов HTTP-ответов в читаемое текстовое сообщение.
    Используется для формирования уведомлений о смене статусов URL, включая
    время проверки, предыдущий и текущий статусы, сообщение и описание ошибки.

    Классы:
    --------
    - HttpProblemFormatter: Реализация Formatter для форматирования данных
      об изменениях HTTP-статусов. Ожидает входной словарь с ключами
      'headers' и 'data', где data — список строк изменений, каждая строка
      содержит: URL, время, предыдущий статус, текущий статус, сообщение,
      описание. Возвращает структурированный текст с разделителями.

    Ключевые зависимости:
    ----------------------
    - .formatter.Formatter: Абстрактный базовый класс форматтеров.
    - typing: Для аннотаций типов.

    Пример использования:
    ----------------------
    changes = {
        'headers': ['Url сайта', 'Время проверки', 'Прошлый статус',
                    'Текущий статус', 'Сообщение', 'Описание'],
        'data': [
            ['https://example.com', datetime.now(), 500, 200,
             'Internal Server Error', 'OK']
        ]
    }
    formatter = HttpProblemFormatter()
    message = formatter.format(changes)
    print(message)  # Выведет отформатированное сообщение
"""
from .formatter import Formatter
from typing import Dict, Any
import logging


logger = logging.getLogger(__name__)


class HttpProblemFormatter(Formatter):
    """
    Форматтер для уведомлений об изменениях HTTP-статусов.

    Кратко:
        Преобразует данные об изменениях статусов URL, полученные от
        HttpResponseAnalyzer, в структурированное текстовое сообщение.
        Каждое изменение оформляется в виде блока с разделителями,
        включая URL, время проверки, предыдущий статус, текущий статус,
        сообщение и описание. Если список изменений пуст, возвращает
        пустую строку.

    Public methods:
        format(changes: Dict[str, Any]) -> str:
            Принимает словарь с ключами 'headers' и 'data', возвращает
            отформатированное сообщение или пустую строку, если изменений нет.

    Behavior notes:
        - Для каждого изменения создаётся блок с разделителями "————————————".
        - Первый блок не содержит пустой строки перед собой.
        - Поле с текущим статусом выделяется жирным шрифтом (двойные звёздочки).
        - Если какой-либо из статусов (предыдущий или текущий) равен None,
          заменяется на "—".
        - Время форматируется в формате 'YYYY-MM-DD HH:MM:SS'.

    Пример:
        changes = {
            'headers': [...],
            'data': [
                ['https://example.com', datetime(2025,3,24,10,30), 500, 200,
                 'Internal Server Error', 'OK']
            ]
        }
        formatter = HttpProblemFormatter()
        print(formatter.format(changes))
        # Выведет:
        # Изменения статусов url:
        # Url сайта:
        # https://example.com
        # ————————————
        # Время проверки:
        # 2025-03-24 10:30:00
        # ...
    """
    def format(self, changes: Dict[str, Any]) -> str:
        """
        Форматирует данные об изменениях статусов HTTP.

        Аргументы:
            changes (Dict[str, Any]): Словарь, содержащий:
                - 'headers': список заголовков столбцов.
                - 'data': список строк изменений, каждая строка – список из 6 элементов:
                    [url, datetime, prev_status, curr_status, message, description].

        Возвращаемое значение:
            str: Отформатированное сообщение с изменениями или пустая строка,
                 если changes['data'] пуст.

        Примечания:
            - Если предыдущий или текущий статус равен None, заменяется на "—".
            - Текущий статус выделяется жирным шрифтом (обрамляется **).
            - Время форматируется в локальный формат 'YYYY-MM-DD HH:MM:SS'.
            - Разделители "————————————" вставляются между полями и после каждого изменения.
        """
        logger.debug("HttpProblemFormatter: formatting %d changes", len(changes.get('data', [])))
        if changes["data"] == []:
            return ''
        lines = ["Изменения статусов url:"]
        for index, row in enumerate(changes['data']):
            if index != 0:
                lines.append("————————————\n")
            url = row[0]
            prev = row[2] if row[2] is not None else "—"
            curr = row[3] if row[3] is not None else "—"
            lines.append(f"{changes['headers'][0]}:")
            lines.append(f"{url:<40}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][1]}:")
            lines.append(f"{row[1].strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][2]}:")
            lines.append(f"{prev}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][3]}:")
            lines.append(f"**{curr}**")
            lines.append("————————————")
            lines.append(f"{changes['headers'][4]}:")
            lines.append(f"{row[4]:<20}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][5]}:")
            lines.append(f"{row[5]}")
        return "\n".join(lines)
