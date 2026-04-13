import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DailyStatsFormatter:
    def format(self, http_stats: Dict[str, tuple], proxmox_vms: List[Dict[str, Any]], interval: int) -> str:
        lines = []
        lines.append(f"Сводка – {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        lines.append("HTTP-сервисы")
        http_section = self._format_http_section(http_stats, interval)
        if http_section is None:
            logger.warning("No HTTP statistics received, possible worker failure")
            lines.append("ВНИМАНИЕ: данные от HTTP не получены (ошибка воркера)")
        else: 
            lines.append(http_section)
        lines.append("")

        lines.append("Виртуальные машины")
        proxmox_section = self._format_proxmox_section(proxmox_vms)
        if proxmox_section is None:
            logger.warning("No Proxmox data received, possible worker failure")
            lines.append("ВНИМАНИЕ: данные от Proxmox не получены (ошибка воркера)")
        else:
            lines.append(proxmox_section)
        return "\n".join(lines)

    def _format_http_section(self, http_stats: Dict[str, tuple], interval: int) -> Optional[str]:
        if not http_stats:
            return None

        now = datetime.now()
        day_seconds = 24 * 60 * 60
        lines = []
        problematic = []
        stable = []

        for url, (last_ts, fail_count) in http_stats.items():
            if last_ts is None:
                uptime_str = "нет успешных проверок"
                problematic.append((url, fail_count, uptime_str))
            else:
                try:
                    last_dt = datetime.fromisoformat(last_ts)
                except Exception:
                    logger.warning("Invalid timestamp format for %s: %s", url, last_ts)
                    continue
                uptime_seconds = (now - last_dt).total_seconds()
                uptime_str = self._format_uptime(int(uptime_seconds))

                if uptime_seconds < day_seconds:
                    problematic.append((url, fail_count, uptime_str))
                else:
                    stable.append((url, uptime_str))

        if problematic:
            lines.append("Проблемные сервисы (Uptime < 24 ч):")
            for url, fail_count, uptime_str in problematic:
                lines.append(f"{url} – отказов: {fail_count} (Uptime {uptime_str})")
        else:
            lines.append("Все сервисы работали стабильно.")

        if stable:
            if problematic:
                lines.append("")
                lines.append("Сервисы без сбоев (Uptime > 24 ч):")
            else:
                lines.append("Сервисы без сбоев:")
            for url, uptime_str in stable:
                lines.append(f"Website: {url}\nUptime: {uptime_str}")

        return "\n".join(lines)

    def _format_proxmox_section(self, vms: List[Dict[str, Any]]) -> Optional[str]:
        if not vms:
            return None

        lines = []
        for vm in vms:
            uptime_str = self._format_uptime(vm['uptime'])
            line = f"{vm['name']} (ID {vm['vmid']}) - Uptime: {uptime_str}"
            if vm.get('problem_changes', 0) > 0:
                line += f" (проблемных изменений за сутки: {vm['problem_changes']})"
            lines.append(line)

        return "\n".join(lines)
    
    def _format_uptime(self, seconds: int, short: bool = True) -> str:
        if seconds is None:
            return "—"
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

    def _format_time(self, dt_str: str) -> str:
        if dt_str is None:
            logger.warning("Failes to format time: received None")
            return "-:-"
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime('%H:%M')
        except Exception as e:
            logger.warning("Failed to parse time '%s': %s", dt_str, e)
            return "-:-"