"""
    Модуль fake_http_response_analyzer.py

    Данный модуль определяет класс FakeHttpResponseAnalyzer, 
    который наследуется от класса HttpResponseAnalyzer и изменяет логику для возврата информации
    Даже если статусы не поменялись будет возвращать сравнение статусов
"""

from analyzers.http_response_analyzer import HttpResponseAnalyzer
from typing import Dict, Any


class FakeHttpResponseAnalyzer(HttpResponseAnalyzer):
    def compare_statuses(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        data = []
        if self.previous_data is None:
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

            prev_status = prev.get("status_code") if prev else None
            curr_status = curr.get("status_code") if curr else None
            data.append([url, curr.get("date"), prev_status, curr_status, curr.get("message") + '/' + prev.get("message"), curr.get("description") + "/" + prev.get("description")])

        return {
            'headers': ['Url сайта', 'Время проверки', 'Прошлый статус', 'Текущий статус', 'Сообщение', 'Описание'],
            'data': data
        }