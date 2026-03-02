"""
OS Tools — SSH Üzerinden İşletim Sistemi Araçları
══════════════════════════════════════════════════
SSH bağlantısı üzerinden:
  - Servis durumu kontrolü (systemctl status)
  - Servis logları okuma (journalctl)
  - Sistem bilgisi (uptime, memory, disk)
  - Process listesi
  - Log dosyası okuma
  - Servis yeniden başlatma (onay gerektirir)

Güvenlik:
  - forbidden_os_commands listesine göre engelleme
  - Riskli operasyonlar Telegram onayı gerektirir
  - Tüm komutlar audit log'a yazılır
"""

import logging
import re
from typing import Any, Dict, List, Optional

from dba_agent.config import get_config, SSHTarget
from dba_agent.tools.registry import ToolDef, get_tool_registry
from dba_agent.tools.ssh_executor import SSHExecutor, SSHResult

logger = logging.getLogger("dba_agent.tools.os_tools")


# ─────────────────────────────────────────────
# SSH Target Helper
# ─────────────────────────────────────────────

def _get_ssh_target(ssh_target: Optional[str] = None) -> SSHTarget:
    """
    SSH target adından SSHTarget döndür.
    None ise ilk target kullanılır.

    Kaynak sırası:
    1. SSHConfig.targets (db_targets.json ssh_enabled olanlar + env)
    2. DatabaseConfig.targets'dan ssh_enabled olanlar (ek fallback)
    """
    config = get_config()
    targets = config.ssh.targets

    # db_targets.json'dan SSH etkin DB target'ları da ekle (duplikasyonu önle)
    existing_hosts = {t.host for t in targets}
    for dt in config.database.targets:
        if dt.ssh_enabled and dt.ssh_host and dt.ssh_host not in existing_hosts:
            targets.append(SSHTarget(
                name=dt.name,
                host=dt.ssh_host,
                user=dt.ssh_user or "root",
                port=dt.ssh_port,
                key_path=dt.ssh_key_path,
                password=dt.ssh_password,
                role="database",
            ))
            existing_hosts.add(dt.ssh_host)

    if not targets:
        raise ValueError(
            "SSH hedefi yapılandırılmamış. "
            "Settings → DB Bağlantıları'ndan SSH bilgilerini ekleyin "
            "veya DBA_SSH_HOST env değişkenini tanımlayın."
        )

    if ssh_target is None:
        return targets[0]

    for t in targets:
        if t.name == ssh_target or t.host == ssh_target:
            return t

    available = [t.name for t in targets]
    raise ValueError(f"SSH target '{ssh_target}' bulunamadı. Mevcut: {available}")


def _get_executor(target: SSHTarget) -> SSHExecutor:
    """SSHExecutor oluştur."""
    config = get_config()
    return SSHExecutor(target, timeout=config.ssh.command_timeout)


# ─────────────────────────────────────────────
# Tool Fonksiyonları
# ─────────────────────────────────────────────

def check_service_status(service_name: str, ssh_target: str = None) -> Dict[str, Any]:
    """
    Bir servisin durumunu kontrol et (systemctl status).

    Args:
        service_name: Servis adı (postgresql, mysql, nginx, vb.)
        ssh_target: SSH hedef adı (None = varsayılan)

    Returns:
        {"service": str, "active": bool, "status": str, "details": str, ...}
    """
    target = _get_ssh_target(ssh_target)

    # Servis izinli mi?
    if target.allowed_services and service_name not in target.allowed_services:
        return {
            "service": service_name,
            "active": None,
            "status": "forbidden",
            "details": f"Servis '{service_name}' izin listesinde değil. "
                       f"İzinli: {target.allowed_services}",
        }

    executor = _get_executor(target)
    result = executor.run(f"systemctl status {service_name} --no-pager -l")

    # Parse
    active = False
    status_text = "unknown"
    if result.success:
        for line in result.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("Active:"):
                status_text = line_stripped
                active = "active (running)" in line_stripped
                break

    return {
        "service": service_name,
        "host": target.host,
        "active": active,
        "status": status_text,
        "details": result.stdout[:2000] if result.success else result.stderr[:1000],
        "exit_code": result.exit_code,
    }


def read_service_logs(
    service_name: str,
    lines: int = 50,
    since: str = "1h",
    ssh_target: str = None,
) -> Dict[str, Any]:
    """
    Servis loglarını oku (journalctl).

    Args:
        service_name: Servis adı
        lines: Okunacak satır sayısı (max 200)
        since: Zaman filtresi (1h, 30m, 1d)
        ssh_target: SSH hedef adı

    Returns:
        {"service": str, "log_lines": List[str], "total_lines": int, ...}
    """
    target = _get_ssh_target(ssh_target)
    lines = min(lines, 200)  # Güvenlik limiti

    executor = _get_executor(target)
    cmd = f"journalctl -u {service_name} --no-pager -n {lines} --since '{since} ago' 2>/dev/null"
    result = executor.run(cmd)

    log_lines = result.stdout.splitlines() if result.success else []

    # Hata/uyarı satırlarını işaretle
    error_count = sum(
        1 for l in log_lines
        if re.search(r'\b(error|fatal|critical|fail|panic)\b', l, re.IGNORECASE)
    )
    warning_count = sum(
        1 for l in log_lines
        if re.search(r'\b(warn|warning)\b', l, re.IGNORECASE)
    )

    return {
        "service": service_name,
        "host": target.host,
        "log_lines": log_lines[-lines:],
        "total_lines": len(log_lines),
        "error_count": error_count,
        "warning_count": warning_count,
        "since": since,
        "success": result.success,
        "error": result.stderr[:500] if not result.success else None,
    }


def get_system_info(ssh_target: str = None) -> Dict[str, Any]:
    """
    Genel sistem bilgisi topla.

    Returns:
        {"hostname": str, "uptime": str, "os": str, "kernel": str,
         "cpu_count": int, "memory": {...}, "disk": {...}, "load_avg": str}
    """
    target = _get_ssh_target(ssh_target)
    executor = _get_executor(target)

    info = {"host": target.host}

    # Hostname
    r = executor.run("hostname")
    info["hostname"] = r.stdout.strip() if r.success else "?"

    # OS / Kernel
    r = executor.run("uname -a")
    info["kernel"] = r.stdout.strip() if r.success else "?"

    r = executor.run("cat /etc/os-release 2>/dev/null | head -3")
    if r.success:
        for line in r.stdout.splitlines():
            if line.startswith("PRETTY_NAME="):
                info["os"] = line.split("=", 1)[1].strip('"')
                break

    # Uptime + Load
    r = executor.run("uptime")
    info["uptime"] = r.stdout.strip() if r.success else "?"

    # CPU count
    r = executor.run("nproc")
    info["cpu_count"] = int(r.stdout.strip()) if r.success else 0

    # Memory
    r = executor.run("free -m | head -3")
    if r.success:
        lines = r.stdout.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                info["memory"] = {
                    "total_mb": int(parts[1]),
                    "used_mb": int(parts[2]),
                    "free_mb": int(parts[3]),
                    "usage_pct": round(int(parts[2]) / max(int(parts[1]), 1) * 100, 1),
                }

    # Disk
    r = executor.run("df -h / | tail -1")
    if r.success:
        parts = r.stdout.strip().split()
        if len(parts) >= 5:
            info["disk"] = {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "usage_pct": parts[4],
            }

    # Load Average
    r = executor.run("cat /proc/loadavg")
    if r.success:
        parts = r.stdout.strip().split()
        if len(parts) >= 3:
            info["load_avg"] = {
                "1min": float(parts[0]),
                "5min": float(parts[1]),
                "15min": float(parts[2]),
            }

    return info


def check_disk_space(ssh_target: str = None) -> Dict[str, Any]:
    """
    Disk kullanımını detaylı kontrol et.

    Returns:
        {"filesystems": List[Dict], "critical": List[str], "warnings": List[str]}
    """
    target = _get_ssh_target(ssh_target)
    executor = _get_executor(target)

    r = executor.run("df -h --output=source,size,used,avail,pcent,target 2>/dev/null || df -h")
    if not r.success:
        return {"error": r.stderr[:500], "filesystems": []}

    lines = r.stdout.strip().splitlines()
    filesystems = []
    critical = []
    warnings = []

    for line in lines[1:]:  # Header atla
        parts = line.split()
        if len(parts) >= 6:
            pct_str = parts[4].rstrip("%")
            try:
                pct = int(pct_str)
            except ValueError:
                pct = 0

            fs = {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "usage_pct": pct,
                "mount": parts[5],
            }
            filesystems.append(fs)

            if pct >= 95:
                critical.append(f"{parts[5]} ({pct}%)")
            elif pct >= 85:
                warnings.append(f"{parts[5]} ({pct}%)")

    return {
        "host": target.host,
        "filesystems": filesystems,
        "critical": critical,
        "warnings": warnings,
        "total_count": len(filesystems),
    }


def check_process_list(
    filter_name: str = "",
    ssh_target: str = None,
) -> Dict[str, Any]:
    """
    Process listesini getir. Opsiyonel filtre.

    Args:
        filter_name: Process adı filtresi (boşsa top 20 by CPU)
        ssh_target: SSH hedef adı

    Returns:
        {"processes": List[Dict], "total": int}
    """
    target = _get_ssh_target(ssh_target)
    executor = _get_executor(target)

    if filter_name:
        cmd = f"ps aux | head -1 && ps aux | grep -i '{filter_name}' | grep -v grep | head -30"
    else:
        cmd = "ps aux --sort=-%cpu | head -21"

    r = executor.run(cmd)
    if not r.success:
        return {"error": r.stderr[:500], "processes": [], "total": 0}

    lines = r.stdout.strip().splitlines()
    processes = []

    for line in lines[1:]:  # Header atla
        parts = line.split(None, 10)
        if len(parts) >= 11:
            processes.append({
                "user": parts[0],
                "pid": parts[1],
                "cpu_pct": float(parts[2]),
                "mem_pct": float(parts[3]),
                "vsz": parts[4],
                "rss": parts[5],
                "stat": parts[7],
                "start": parts[8],
                "time": parts[9],
                "command": parts[10][:120],
            })

    return {
        "host": target.host,
        "processes": processes,
        "total": len(processes),
        "filter": filter_name or "(top by CPU)",
    }


def read_os_log(
    log_path: str,
    lines: int = 50,
    grep_pattern: str = "",
    ssh_target: str = None,
) -> Dict[str, Any]:
    """
    OS log dosyası oku.

    Args:
        log_path: Log dosya yolu (/var/log/postgresql/postgresql-*.log, vb.)
        lines: Satır sayısı (max 200)
        grep_pattern: Filtre deseni (opsiyonel)
        ssh_target: SSH hedef adı

    Returns:
        {"log_path": str, "log_lines": List[str], ...}
    """
    target = _get_ssh_target(ssh_target)
    executor = _get_executor(target)
    lines = min(lines, 200)

    # Güvenlik: log_path'te tehlikeli karakterler kontrolü
    if any(c in log_path for c in [";", "|", "&", "$", "`", "(", ")"]):
        return {
            "error": "Güvenlik: Log yolu geçersiz karakterler içeriyor.",
            "log_path": log_path,
            "log_lines": [],
        }

    if grep_pattern:
        cmd = f"tail -n {lines * 3} '{log_path}' 2>/dev/null | grep -i '{grep_pattern}' | tail -n {lines}"
    else:
        cmd = f"tail -n {lines} '{log_path}' 2>/dev/null"

    r = executor.run(cmd)

    log_lines = r.stdout.splitlines() if r.success else []
    error_count = sum(
        1 for l in log_lines
        if re.search(r'\b(ERROR|FATAL|PANIC)\b', l)
    )

    return {
        "host": target.host,
        "log_path": log_path,
        "log_lines": log_lines,
        "total_lines": len(log_lines),
        "error_count": error_count,
        "grep_pattern": grep_pattern or None,
        "success": r.success,
        "error": r.stderr[:500] if not r.success else None,
    }


def restart_service(
    service_name: str,
    ssh_target: str = None,
) -> Dict[str, Any]:
    """
    Servisi yeniden başlat (systemctl restart).
    ⚠️ HIGH risk — Telegram onayı gerektirir.

    Args:
        service_name: Servis adı
        ssh_target: SSH hedef adı

    Returns:
        {"service": str, "restarted": bool, "message": str}
    """
    target = _get_ssh_target(ssh_target)

    # Servis izinli mi?
    if target.allowed_services and service_name not in target.allowed_services:
        return {
            "service": service_name,
            "restarted": False,
            "message": f"Servis '{service_name}' izin listesinde değil. "
                       f"İzinli: {target.allowed_services}",
        }

    executor = _get_executor(target)

    # Restart öncesi durum al
    pre_status = executor.run(f"systemctl is-active {service_name}")
    pre_active = pre_status.stdout.strip() if pre_status.success else "unknown"

    # Restart
    result = executor.run(f"sudo systemctl restart {service_name}")

    if not result.success:
        return {
            "service": service_name,
            "host": target.host,
            "restarted": False,
            "pre_status": pre_active,
            "message": f"Restart başarısız: {result.stderr[:500]}",
        }

    # Restart sonrası durum kontrol (2s bekle)
    import time
    time.sleep(2)
    post_status = executor.run(f"systemctl is-active {service_name}")
    post_active = post_status.stdout.strip() if post_status.success else "unknown"

    return {
        "service": service_name,
        "host": target.host,
        "restarted": post_active == "active",
        "pre_status": pre_active,
        "post_status": post_active,
        "message": f"Servis {'başarıyla yeniden başlatıldı' if post_active == 'active' else 'başlatılamadı'}",
    }


def check_port(port: int, ssh_target: str = None) -> Dict[str, Any]:
    """
    Port durumunu kontrol et (netstat/ss).

    Args:
        port: Port numarası
        ssh_target: SSH hedef adı

    Returns:
        {"port": int, "listening": bool, "details": str}
    """
    target = _get_ssh_target(ssh_target)
    executor = _get_executor(target)

    r = executor.run(f"ss -tlnp 2>/dev/null | grep ':{port} ' || netstat -tlnp 2>/dev/null | grep ':{port} '")

    listening = bool(r.stdout.strip()) if r.success else False

    return {
        "host": target.host,
        "port": port,
        "listening": listening,
        "details": r.stdout.strip()[:500] if r.success else r.stderr[:500],
    }


# ─────────────────────────────────────────────
# Tool Registration
# ─────────────────────────────────────────────

def register_os_tools() -> None:
    """OS araçlarını registry'ye kaydet."""
    registry = get_tool_registry()

    tools = [
        ToolDef(
            name="check_service_status",
            description="Servis durumunu kontrol et (systemctl status)",
            category="os",
            func=check_service_status,
            args_schema={
                "service_name": "str — Servis adı (postgresql, mysql, nginx...)",
                "ssh_target": "str|None — SSH hedef adı (varsayılan: ilk target)",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="read_service_logs",
            description="Servis loglarını oku (journalctl)",
            category="os",
            func=read_service_logs,
            args_schema={
                "service_name": "str — Servis adı",
                "lines": "int — Satır sayısı (varsayılan: 50, max: 200)",
                "since": "str — Zaman filtresi (varsayılan: 1h)",
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="get_system_info",
            description="Genel sistem bilgisi (hostname, OS, CPU, RAM, disk, uptime)",
            category="os",
            func=get_system_info,
            args_schema={
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="check_disk_space",
            description="Disk kullanımını detaylı kontrol et",
            category="os",
            func=check_disk_space,
            args_schema={
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="check_process_list",
            description="Process listesini getir (CPU sıralı veya filtreli)",
            category="os",
            func=check_process_list,
            args_schema={
                "filter_name": "str — Process adı filtresi (boş = top 20 by CPU)",
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="read_os_log",
            description="OS log dosyası oku (tail + grep)",
            category="os",
            func=read_os_log,
            args_schema={
                "log_path": "str — Log dosya yolu (/var/log/...)",
                "lines": "int — Satır sayısı (varsayılan: 50)",
                "grep_pattern": "str — Filtre deseni (opsiyonel)",
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
        ToolDef(
            name="restart_service",
            description="Servisi yeniden başlat (systemctl restart) ⚠️ ONAY GEREKTİRİR",
            category="os",
            func=restart_service,
            args_schema={
                "service_name": "str — Servis adı",
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="high",
            requires_ssh=True,
        ),
        ToolDef(
            name="check_port",
            description="Port dinleniyor mu kontrol et (ss/netstat)",
            category="os",
            func=check_port,
            args_schema={
                "port": "int — Port numarası",
                "ssh_target": "str|None — SSH hedef adı",
            },
            risk_level="safe",
            requires_ssh=True,
        ),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(f"OS tools registered: {len(tools)} araç")
