"""
    Модуль proxmox_formatter.py

    Данный модуль определяет класс ProxmoxFormatter, который форматирует данные
    об изменениях статусов виртуальных машин Proxmox в читаемое текстовое сообщение.
    Используется для формирования уведомлений о смене статусов ВМ, включая
    дополнительную информацию: время проверки, предыдущий и текущий статусы,
    а также детали о каждой ВМ (VMID, Node, Type, Uptime, сетевой трафик).

    Классы:
    --------
    - ProxmoxFormatter: Реализация Formatter для форматирования данных
      об изменениях ВМ. Ожидает входной словарь с ключами 'headers', 'data' и
      'vmid_info', где data — список строк изменений, каждая строка содержит:
      имя ВМ, предыдущий статус, текущий статус. Дополнительно из vmid_info
      извлекаются детали (uptime, сеть и др.). Возвращает структурированный
      текст с разделителями.

    Ключевые зависимости:
    ----------------------
    - .formatter.Formatter: Абстрактный базовый класс форматтеров.
    - typing: Для аннотаций типов.

    Пример использования:
    ----------------------
    changes = {
        'timestamp': datetime.now(),
        'headers': ['Название ВМ', 'Прошлый статус', 'Текущий статус'],
        'data': [
            ['vm-web', 'stopped', 'running']
        ],
        'vmid_info': [
            {
                'vmid': 100,
                'node': 'pve1',
                'type': 'qemu',
                'uptime': 123456,
                'netin_bytes': 1024,
                'netout_bytes': 512
            }
        ]
    }
    formatter = ProxmoxFormatter()
    message = formatter.format(changes)
    print(message)  # Выведет отформатированное сообщение с деталями ВМ
"""
from formatters.formatter import Formatter
from typing import Any, Dict
import logging


logger = logging.getLogger(__name__)


class ProxmoxFormatter(Formatter):
    """
    Форматтер для уведомлений об изменениях статусов ВМ Proxmox.

    Кратко:
        Преобразует данные об изменениях статусов ВМ, полученные от
        ProxmoxAnalyzer, в структурированное текстовое сообщение.
        Каждое изменение оформляется в виде блока с разделителями,
        включая имя ВМ, предыдущий и текущий статусы, а также детальную
        информацию: VMID, нода, тип, аптайм, входящий/исходящий трафик.
        Если список изменений пуст, возвращает пустую строку.

    Public methods:
        format(changes: Dict[str, Any]) -> str:
            Принимает словарь с ключами 'timestamp', 'headers', 'data', 'vmid_info',
            возвращает отформатированное сообщение или пустую строку, если изменений нет.

    Вспомогательные методы:
        _format_uptime(seconds: int) -> str:
            Преобразует секунды в строку вида 'Xд Yч Zм'.
        _format_bytes(bytes_val: int) -> str:
            Преобразует байты в читаемый формат (Б, КБ, МБ, ГБ, ТБ).

    Behavior notes:
        - Для каждого изменения создаётся блок с разделителями "————————————".
        - Первый блок не содержит пустой строки перед собой.
        - Время проверки выводится в формате 'YYYY-MM-DD HH:MM:SS'.
        - Если аптайм или сетевые данные отсутствуют (None), заменяется на "N/A".
        - Детали ВМ выводятся в виде строки с переносами.

    Пример:
        changes = {
            'timestamp': datetime(2025,3,24,10,30),
            'headers': ['Название ВМ', 'Прошлый статус', 'Текущий статус'],
            'data': [['vm-web', 'stopped', 'running']],
            'vmid_info': [{'vmid':100, 'node':'pve1', 'type':'qemu', 'uptime':123456,
                           'netin_bytes':1024, 'netout_bytes':512}]
        }
        formatter = ProxmoxFormatter()
        print(formatter.format(changes))
        # Выведет:
        # Время проверки: 2025-03-24 10:30:00
        # Изменения статусов ВМ в Proxmox:
        # Название ВМ:
        # vm-web
        # ————————————
        # Прошлый статус:
        # stopped
        # ————————————
        # Текущий статус:
        # running
        # ————————————
        # VMID: 100,
        # Node: pve1,
        # Type: qemu,
        # Uptime: 1д 10ч 17м,
        # NetIn: 1.0 КБ,
        # NetOut: 512 Б
    """
    def _format_uptime(self, seconds: int) -> str:
        """Преобразует секунды в строку вида 'Xд Yч Zм'."""
        if seconds is None:
            return "N/A"
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days > 0:
            parts.append(f"{days}д")
        if hours > 0:
            parts.append(f"{hours}ч")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}м")
        return " ".join(parts)
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Преобразует байты в читаемый формат (Б, КБ, МБ, ГБ, ТБ)."""
        if bytes_val is None:
            return "N/A"
        for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} ПБ"
    
    def format(self, changes: Dict[str, Any]) -> str:
        """
        Форматирует данные об изменениях статусов ВМ.

        Аргументы:
            changes (Dict[str, Any]): Словарь, содержащий:
                - 'timestamp' (datetime): время проверки.
                - 'headers' (List[str]): заголовки столбцов.
                - 'data' (List[List]): список строк изменений, каждая строка — [name, prev_status, curr_status].
                - 'vmid_info' (List[Dict]): список словарей с деталями ВМ (vmid, node, type, uptime,
                  netin_bytes, netout_bytes) для каждой изменённой ВМ.

        Возвращаемое значение:
            str: Отформатированное сообщение с изменениями или пустая строка,
                 если changes['data'] пуст.

        Примечания:
            - Для каждой ВМ из 'data' извлекается соответствующий элемент из 'vmid_info'
              (по индексу).
            - Аптайм и сетевые данные форматируются с помощью _format_uptime и _format_bytes.
            - В случае отсутствия данных (None) выводится "N/A".
        """
        logger.debug("ProxmoxFormatter: formatting %d changes", len(changes.get('data', [])))
        timestamp = changes.get('timestamp')
        lines = []
        if changes["data"] == []:
            return ''
        lines.append(f"Время проверки: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("Изменения статусов ВМ в Proxmox:\n")
        for index, row in enumerate(changes['data']):
            if index != 0:
                lines.append("————————————\n")
            lines.append(f"{changes['headers'][0]}:")
            lines.append(f"{row[0]}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][1]}:")
            lines.append(f"{row[1]}")
            lines.append("————————————")
            lines.append(f"{changes['headers'][2]}:")
            lines.append(f"{row[2]}")
            lines.append("————————————")
            vm = changes["vmid_info"][index]
            uptime_str = self._format_uptime(vm.get('uptime'))
            netin_str = self._format_bytes(vm.get('netin_bytes'))
            netout_str = self._format_bytes(vm.get('netout_bytes'))
            extra = (
                f"VMID: {vm['vmid']},\nNode: {vm['node']},\nType: {vm['type']},\n"
                f"Uptime: {uptime_str},\nNetIn: {netin_str},\nNetOut: {netout_str}"
            )
            lines.append(extra)
        
        return "\n".join(lines)
