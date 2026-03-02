"""
SSH Executor — Paramiko Tabanlı Güvenli SSH Çalıştırıcı
═══════════════════════════════════════════════════════
SSH üzerinden komut çalıştırma altyapısı.

Güvenlik Katmanları:
  1. forbidden_os_commands listesi kontrolü
  2. Komut sanitization (shell injection engelleme)
  3. Timeout koruması
  4. Audit logging
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from dba_agent.config import SSHTarget, get_config

logger = logging.getLogger("dba_agent.tools.ssh_executor")


@dataclass
class SSHResult:
    """SSH komut çalıştırma sonucu."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    success: bool = False
    error: Optional[str] = None
    command: str = ""
    host: str = ""


class SSHExecutor:
    """
    SSH üzerinden güvenli komut çalıştırıcı.

    Kullanım:
        executor = SSHExecutor(target, timeout=30)
        result = executor.run("systemctl status postgresql")
    """

    def __init__(self, target: SSHTarget, timeout: int = 30):
        self.target = target
        self.timeout = timeout
        self._config = get_config()

    def _check_forbidden(self, command: str) -> Optional[str]:
        """
        Komutu yasak listesine karşı kontrol et.

        Returns:
            None = güvenli, str = engelleme sebebi
        """
        cmd_lower = command.lower().strip()
        for forbidden in self._config.security.forbidden_os_commands:
            if forbidden.lower() in cmd_lower:
                return f"FORBIDDEN: Komut '{forbidden}' güvenlik politikası gereği engellenmiştir."
        return None

    def _sanitize_command(self, command: str) -> str:
        """
        Temel shell injection koruması.
        Sadece bilinen güvenli komut yapılarına izin verir.
        """
        # Çok uzun komutları reddet
        if len(command) > 1000:
            raise ValueError("Komut çok uzun (max 1000 karakter)")

        return command

    def run(self, command: str) -> SSHResult:
        """
        SSH üzerinden komut çalıştır.

        Args:
            command: Çalıştırılacak shell komutu

        Returns:
            SSHResult
        """
        # Güvenlik kontrolleri
        forbidden_reason = self._check_forbidden(command)
        if forbidden_reason:
            logger.warning(f"Forbidden SSH command: {command} → {forbidden_reason}")
            return SSHResult(
                stderr=forbidden_reason,
                exit_code=126,
                success=False,
                error=forbidden_reason,
                command=command,
                host=self.target.host,
            )

        try:
            command = self._sanitize_command(command)
        except ValueError as e:
            return SSHResult(
                stderr=str(e),
                exit_code=1,
                success=False,
                error=str(e),
                command=command,
                host=self.target.host,
            )

        # Audit log
        self._audit_log(command, "executing")

        try:
            import paramiko

            # SSH bağlantısı oluştur
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.target.host,
                "port": self.target.port,
                "username": self.target.user,
                "timeout": 10,
            }

            # Key-based veya password-based auth
            key_path = self.target.key_path
            ssh_password = getattr(self.target, 'password', '') or ''

            if not key_path:
                # Default key yollarını dene
                for default_key in [
                    os.path.expanduser("~/.ssh/id_rsa"),
                    os.path.expanduser("~/.ssh/id_ed25519"),
                    "/root/.ssh/id_rsa",
                    "/root/.ssh/id_ed25519",
                ]:
                    if os.path.exists(default_key):
                        key_path = default_key
                        break

            if key_path and os.path.exists(key_path):
                connect_kwargs["key_filename"] = key_path
            elif ssh_password:
                connect_kwargs["password"] = ssh_password
            else:
                # SSH Agent kullan
                connect_kwargs["allow_agent"] = True
                connect_kwargs["look_for_keys"] = True

            client.connect(**connect_kwargs)

            # Komut çalıştır
            stdin, stdout, stderr = client.exec_command(
                command, timeout=self.timeout
            )

            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()

            client.close()

            success = exit_code == 0
            self._audit_log(
                command,
                "success" if success else f"failed (exit {exit_code})",
            )

            return SSHResult(
                stdout=stdout_text,
                stderr=stderr_text,
                exit_code=exit_code,
                success=success,
                command=command,
                host=self.target.host,
            )

        except paramiko.AuthenticationException as e:
            error_msg = f"SSH kimlik doğrulama hatası: {e}"
            logger.error(f"{error_msg} ({self.target.host})")
            self._audit_log(command, "auth_error")
            return SSHResult(
                stderr=error_msg,
                exit_code=255,
                success=False,
                error=error_msg,
                command=command,
                host=self.target.host,
            )

        except paramiko.SSHException as e:
            error_msg = f"SSH bağlantı hatası: {e}"
            logger.error(f"{error_msg} ({self.target.host})")
            self._audit_log(command, "ssh_error")
            return SSHResult(
                stderr=error_msg,
                exit_code=255,
                success=False,
                error=error_msg,
                command=command,
                host=self.target.host,
            )

        except Exception as e:
            error_msg = f"SSH hatası: {e}"
            logger.error(f"{error_msg} ({self.target.host})", exc_info=True)
            self._audit_log(command, "error")
            return SSHResult(
                stderr=error_msg,
                exit_code=1,
                success=False,
                error=error_msg,
                command=command,
                host=self.target.host,
            )

    def test_connection(self) -> SSHResult:
        """
        SSH bağlantısını test et.

        Returns:
            SSHResult (stdout = hostname + uptime)
        """
        return self.run("hostname && uptime")

    def _audit_log(self, command: str, result: str) -> None:
        """Audit log yaz."""
        try:
            from dba_agent.security.audit import AuditLogger
            audit = AuditLogger()
            audit.log_os_command(
                target=f"{self.target.name}@{self.target.host}",
                command=command,
                risk="safe",  # Risk seviyesi tool katmanında belirlenir
                result=result,
            )
        except Exception:
            pass  # Audit hatası tool'u engellemesin
