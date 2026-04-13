"""
    Модуль fake_proxmox_analyzer.py

    Данный модуль определяет класс FakeProxmoxAnalyzer, 
    который наследуется от класса ProxmoxAnalyzer и изменяет логику для возврата информации
    Даже если статусы не поменялись будет возвращать сравнение статусов
"""

from analyzers.proxmox_analyzer import ProxmoxAnalyzer
from typing import Dict, Any


class FakeProxmoxAnalyzer(ProxmoxAnalyzer):
    def compare_statuses(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        data = []
        vmid_info = []
        curr_vms = {vm['vmid']: vm for vm in current_data.get('virtual_machines', []) if vm.get('vmid') is not None}
        if self.previous_data is None:
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
            vm_name = curr_vms[vmid]['name']
            prev_display = prev_status if prev_status is not None else '— (была создана)'
            curr_display = curr_status if curr_status is not None else '— (удалена)'
            data.append([vm_name, prev_display, curr_display])
            vmid_info.append(curr_vms[vmid])
            
        return {
            'headers': ['Название ВМ', 'Прошлый статус', 'Текущий статус'],
            'data': data,
            'vmid_info': vmid_info
        }