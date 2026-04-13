from typing import Any, Dict, List
import copy
from .analyzer import Analyzer
import logging
"""
    Модуль proxmox_analyzer.py

    Данный модуль определяет класс ProxmoxAnalyzer для анализа данных,
    полученных из Proxmox VE API. Предназначен для извлечения информации о
    виртуальных машинах (QEMU/LXC) и физических узлах (нодах), а также для
    сравнения текущего состояния с предыдущим с целью выявления изменений
    статусов ВМ. Используется в системах мониторинга и отслеживания
    инфраструктуры.

    Классы:
    --------
    - ProxmoxAnalyzer: Класс, наследующий от Analyzer, реализующий логику
      анализа и сравнения данных Proxmox.

    Ключевые зависимости:
    ----------------------
    - .analyzer.Analyzer: Базовый абстрактный класс для анализаторов.
    - copy: Используется для глубокого копирования состояния при сохранении.
    - typing: Для аннотаций типов (Dict, List, Any).

    Пример использования:
    ----------------------
    1. Создайте экземпляр ProxmoxAnalyzer, указав список интересующих нод
       и, при необходимости, предыдущие данные для сравнения.
    2. Вызовите метод analyze, передав словарь с данными от ProxmoxLoader.
    3. Получите результат — словарь с изменениями статусов ВМ и временной меткой.

    Пример реализации:
        analyzer = ProxmoxAnalyzer(nodes=["pve1", "pve2"])
        result = analyzer.analyze(proxmox_data)
        if result["data"]:
            print("Изменения статусов ВМ:")
            for row in result["data"]:
                print(f"{row[0]}: {row[1]} -> {row[2]}")
"""
logger = logging.getLogger(__name__)


class ProxmoxAnalyzer(Analyzer):
    """
    Анализатор данных Proxmox.

    Кратко:
        Класс для обработки и сравнения данных, полученных из Proxmox VE API.
        Извлекает информацию о виртуальных машинах (QEMU, LXC) и физических узлах,
        а также выявляет изменения статусов ВМ по сравнению с предыдущим состоянием.

    Args:
        nodes (List[str]): Список имён нод Proxmox, которые необходимо отслеживать.
        data (Optional[Dict[str, Any]]): Предыдущие данные (результат предыдущего
            анализа) для сравнения. Если None, сравнение не выполняется, а в отчёте
            все ВМ будут помечены как новые.

    Attributes:
        nodes (List[str]): Список отслеживаемых нод.
        previous_data (Optional[Dict[str, Any]]): Сохранённое предыдущее состояние
            анализа (структура как у результата analyze, содержащая 'virtual_machines'
            и 'system_info').

    Public methods:
        analyze(data: Dict[str, Any]) -> Dict[str, Any]:
            Выполняет анализ переданных данных, извлекая информацию о ВМ и узлах,
            а затем сравнивает текущее состояние с предыдущим (если есть).
            Возвращает словарь с изменениями и временной меткой.

        compare_statuses(current_data: Dict[str, Any]) -> Dict[str, Any]:
            Сравнивает текущие данные о ВМ с предыдущими. Возвращает словарь,
            содержащий заголовки таблицы изменений, список строк изменений
            и информацию о затронутых ВМ.

    Behavior notes:
        - Внутренняя структура current_data, формируемая в analyze, содержит ключи
          'virtual_machines' (список словарей с информацией о ВМ) и 'system_info'
          (список словарей с информацией об узлах).
        - Сравнение статусов ВМ выполняется по полю 'status' (running, stopped и т.п.).
        - ВМ, которые отсутствуют в текущих данных, но были в предыдущих, считаются
          удалёнными (статус '— (удалена)').
        - ВМ, которые появились в текущих данных, но не были в предыдущих, считаются
          созданными (статус '— (была создана)').
        - После выполнения analyze текущее состояние сохраняется в previous_data
          (глубокая копия) для последующих сравнений.

    Raises:
        Нет явных исключений; все ошибки обрабатываются внутри (например,
        отсутствие ключей в данных) и приводят к пустым результатам.

    Ключевые зависимости:
        - copy.deepcopy: для сохранения состояния.
        - Анализатор использует структуры данных, возвращаемые ProxmoxLoader.

    Пример использования:
        analyzer = ProxmoxAnalyzer(nodes=["pve1"], data=previous_result)
        current_result = proxmox_loader.get_data(...)
        changes = analyzer.analyze(current_result)
        print(changes["headers"])
        for row in changes["data"]:
            print(row)
    """

    def __init__(self, nodes: List[str], data: Dict[str, Any] = None):
        """
        Инициализирует анализатор Proxmox.

        Args:
            nodes (List[str]): Список имён нод, за которыми ведётся наблюдение.
            data (Optional[Dict[str, Any]]): Предыдущее состояние анализа.
                Ожидается, что это словарь, возвращённый методом analyze
                (с ключами 'virtual_machines' и 'system_info').
        """
        logger.info("ProxmoxAnalyzer initialized for nodes: %s", nodes)
        self.nodes = nodes
        self.previous_data = data

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет анализ данных Proxmox.

        Извлекает из входного словаря (обычно результат работы ProxmoxLoader)
        информацию о виртуальных машинах и узлах, ограничиваясь заданными нодами.
        Затем сравнивает текущее состояние с предыдущим (если оно было сохранено)
        и формирует отчёт об изменениях.

        Args:
            data (Dict[str, Any]): Словарь с данными от ProxmoxLoader.
                Ожидаются ключи:
                    - 'datetime' (datetime): временная метка запроса.
                    - 'data' (List[Dict]): список ресурсов Proxmox.

        Returns:
            Dict[str, Any]: Словарь, содержащий:
                - 'headers' (List[str]): Заголовки таблицы изменений
                  (например, ['Название ВМ', 'Прошлый статус', 'Текущий статус']).
                - 'data' (List[List]): Список строк с изменениями (каждая строка —
                  [имя ВМ, предыдущий статус, текущий статус]).
                - 'vmid_info' (List[Dict]): Список словарей с полной информацией
                  о ВМ, участвовавших в изменениях.
                - 'timestamp' (datetime): Временная метка из входных данных.

        Behavior notes:
            - Метод создаёт внутреннюю структуру current_analysis с ключами
              'virtual_machines' и 'system_info'.
            - Вызывает compare_statuses для получения изменений.
            - Сохраняет текущее состояние в self.previous_data (глубокая копия)
              для последующих вызовов.
        """
        logger.info("ProxmoxAnalyzer: starting analysis")
        timestamp = data.get('datetime') 
        all_resources = data.get('data', [])
        logger.debug("Total resources received: %d", len(all_resources))

        nodes = []
        vms = []

        for resource in all_resources:
            # Фильтрация ВМ (типы qemu/lxc), принадлежащих отслеживаемым нодам
            if resource.get("type") in ("qemu", "lxc") and resource.get('node') in self.nodes:
                vm_info = {
                    'vmid': resource.get('vmid'),
                    'type': resource.get('type'),
                    'name': resource.get('name'),
                    'status': resource.get('status'),
                    'uptime': resource.get('uptime'),
                    'node': resource.get('node'),
                    'netin_bytes': resource.get('netin'),
                    'netout_bytes': resource.get('netout')
                }
                logger.debug("Added VM: %s (vmid=%s)", vm_info['name'], vm_info['vmid'])
                vms.append(vm_info)
            # Фильтрация узлов (тип node)
            if resource.get("type") == "node":
                node_info = {
                    'type': resource.get('type'),
                    'name': resource.get('node'),
                    'cpu_load': resource.get('cpu'),
                    'cpu_cores': resource.get('maxcpu'),
                    'memory_used': resource.get('mem'),
                    'memory_total': resource.get('maxmem'),
                    'disk_used': resource.get('disk'),
                    'disk_total': resource.get('maxdisk'),
                    'uptime': resource.get('uptime')
                }
                logger.debug("Added node: %s", node_info['name'])
                nodes.append(node_info)
        current_analysis = {
            'virtual_machines': vms,
            'system_info': nodes
        }
        logger.info("ProxmoxAnalyzer: extracted %d VMs and %d nodes", len(vms), len(nodes))
        
        changes = self.compare_statuses(current_analysis)
        changes['timestamp'] = timestamp

        self.previous_data = copy.deepcopy(current_analysis)
        logger.info("ProxmoxAnalyzer: analysis completed, found %d status changes", len(changes.get('data', [])))

        return changes

    def compare_statuses(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сравнивает текущие данные о ВМ с предыдущим сохранённым состоянием.

        Args:
            current_data (Dict[str, Any]): Словарь с текущими данными, содержащий
                ключ 'virtual_machines' (список словарей с информацией о ВМ)
                клюя 'system_info' (список словарей с информацией о нодах)

        Returns:
            Dict[str, Any]: Словарь с результатами сравнения:
                - 'headers' (List[str]): Заголовки таблицы (фиксированные).
                - 'data' (List[List]): Список строк изменений. Каждая строка —
                  [имя ВМ, предыдущий статус, текущий статус].
                - 'vmid_info' (List[Dict]): Список словарей с полной информацией
                  о ВМ, для которых обнаружены изменения.

        Behavior notes:
            - Если предыдущие данные отсутствуют (self.previous_data is None),
              все ВМ из current_data считаются новыми. В этом случае для каждой
              ВМ формируется строка с предыдущим статусом '— (нет данных)'.
            - Изменение статуса определяется сравнением поля 'status' у ВМ с
              одинаковым vmid.
            - Если ВМ присутствует только в текущих данных, считается созданной.
            - Если ВМ присутствует только в предыдущих данных, считается удалённой.
        """
        data = []
        vmid_info = []
        curr_vms = {vm['vmid']: vm for vm in current_data.get('virtual_machines', []) if vm.get('vmid') is not None}
        # Если предыдущих данных нет — все ВМ новые
        if self.previous_data is None:
            logger.info("No previous data, treating all VMs as new")
            for vm in curr_vms.values():
                data.append([vm.get('name'), '— (нет данных)', vm.get('status')])
                vmid_info.append(vm)
            return {
                'headers': ['Название ВМ', 'Прошлый статус', 'Текущий статус'],
                'data': data,
                'vmid_info': vmid_info
            }
        prev_vms = {vm['vmid']: vm for vm in self.previous_data.get('virtual_machines', []) if vm.get('vmid') is not None}
        
        all_vmid = set(prev_vms.keys()) | set(curr_vms.keys())
        
        for vmid in sorted(all_vmid):
            prev_status = prev_vms[vmid]['status'] if vmid in prev_vms else None
            curr_status = curr_vms[vmid]['status'] if vmid in curr_vms else None
            # Сравнение статусов между прошлым и настоящим состоянием
            if prev_status != curr_status:
                # Определяем, откуда брать имя ВМ и полную информацию
                if vmid in curr_vms:
                    vm_name = curr_vms[vmid]['name']
                    vm_info = curr_vms[vmid]
                else:
                    vm_name = prev_vms[vmid]['name']
                    vm_info = prev_vms[vmid]
                prev_display = prev_status if prev_status is not None else '— (была создана)'
                curr_display = curr_status if curr_status is not None else '— (удалена)'
                logger.debug("Status change for VM %s: %s -> %s", vm_name, prev_display, curr_display)
                data.append([vm_name, prev_display, curr_display])
                vmid_info.append(vm_info)
        
        return {
            'headers': ['Название ВМ', 'Прошлый статус', 'Текущий статус'],
            'data': data,
            'vmid_info': vmid_info
        }

