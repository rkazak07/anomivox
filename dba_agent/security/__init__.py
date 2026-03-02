"""
Security / SQL Guard
════════════════════
SQL ve OS komutlarının güvenlik kontrolü.
FORBIDDEN kalıpları engeller, risk sınıflandırması yapar.
"""

import logging
import re
from typing import Optional, Tuple

from dba_agent.config import SecurityConfig, get_config
from dba_agent.db.adapter import RiskLevel

logger = logging.getLogger("dba_agent.security")


class SQLGuard:
    """
    SQL komutlarını güvenlik açısından denetler.
    
    Kullanım:
        guard = SQLGuard()
        risk, reason = guard.classify("DROP TABLE users")
        # → (RiskLevel.FORBIDDEN, "DROP TABLE engellendi")
        
        risk, reason = guard.classify("SELECT * FROM pg_stat_activity")
        # → (RiskLevel.SAFE, "Read-only SELECT sorgusu")
    """

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or get_config().security
        self._forbidden_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.forbidden_sql_patterns
        ]

    def classify(self, sql: str) -> Tuple[RiskLevel, str]:
        """
        SQL komutunun risk seviyesini belirle.
        
        Returns:
            (RiskLevel, açıklama)
        """
        clean = sql.strip()
        upper = clean.upper()

        # 1. FORBIDDEN kontrol
        for pattern in self._forbidden_patterns:
            if pattern.search(clean):
                return (
                    RiskLevel.FORBIDDEN,
                    f"⛔ ENGELLENEN kalıp tespit edildi: {pattern.pattern}"
                )

        # 2. SAFE — read-only sorgular
        if self._is_readonly(upper):
            return (RiskLevel.SAFE, "🟢 Read-only sorgu")

        # 3. LOW risk — güvenli DBA operasyonları
        low_risk_patterns = [
            r"CREATE\s+INDEX\s+CONCURRENTLY",
            r"^ANALYZE\b",
            r"^VACUUM\s+ANALYZE\b",
            r"^VACUUM\b(?!.*FULL)",
            r"^REINDEX\s+INDEX\b",
            r"^COMMENT\s+ON\b",
        ]
        for pattern in low_risk_patterns:
            if re.match(pattern, upper):
                return (RiskLevel.LOW, "🟡 Düşük riskli DBA operasyonu")

        # 4. MEDIUM risk — yapısal değişiklikler
        medium_risk_patterns = [
            r"^ALTER\s+TABLE\b",
            r"^CREATE\s+INDEX\b",  # CONCURRENTLY olmayan
            r"^REINDEX\s+TABLE\b",
            r"^VACUUM\s+FULL\b",
            r"^ALTER\s+INDEX\b",
            r"^CLUSTER\b",
        ]
        for pattern in medium_risk_patterns:
            if re.match(pattern, upper):
                return (RiskLevel.MEDIUM, "🟠 Orta riskli yapısal değişiklik")

        # 5. HIGH risk — veri değiştiren/silen
        high_risk_patterns = [
            r"^DROP\s+INDEX\b",
            r"^DELETE\s+FROM\b",
            r"^UPDATE\b",
            r"^INSERT\b",
            r"SELECT\s+PG_TERMINATE_BACKEND",
            r"SELECT\s+PG_CANCEL_BACKEND",
            r"^KILL\b",
        ]
        for pattern in high_risk_patterns:
            if re.match(pattern, upper):
                return (RiskLevel.HIGH, "🔴 Yüksek riskli veri/yapı değiştiren işlem")

        # 6. Bilinmeyen → MEDIUM (güvende kal)
        return (RiskLevel.MEDIUM, "🟠 Sınıflandırılamamış SQL komutu — onay gerektirir")

    def _is_readonly(self, upper: str) -> bool:
        """Read-only sorgu mu?"""
        readonly_prefixes = [
            "SELECT", "EXPLAIN", "SHOW", "\\D", "WITH",
            "TABLE",  # PostgreSQL TABLE komutu
        ]
        for prefix in readonly_prefixes:
            if upper.startswith(prefix):
                # SELECT ... INTO / SELECT ... FOR UPDATE hariç
                if "INTO" in upper or "FOR UPDATE" in upper or "FOR SHARE" in upper:
                    return False
                return True
        return False

    def is_safe(self, sql: str) -> bool:
        """Sorgu güvenli (otomatik çalıştırılabilir) mi?"""
        risk, _ = self.classify(sql)
        return risk == RiskLevel.SAFE

    def is_forbidden(self, sql: str) -> bool:
        """Sorgu yasak mı?"""
        risk, _ = self.classify(sql)
        return risk == RiskLevel.FORBIDDEN


class OSCommandGuard:
    """
    OS komutlarını güvenlik açısından denetler.
    
    Kullanım:
        guard = OSCommandGuard()
        risk, reason = guard.classify("systemctl restart postgresql")
        # → (RiskLevel.HIGH, "Veritabanı servisi restart")
    """

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or get_config().security

    def classify(self, command: str) -> Tuple[RiskLevel, str]:
        """OS komutunun risk seviyesini belirle."""
        clean = command.strip()

        # 1. FORBIDDEN kontrol
        for forbidden in self.config.forbidden_os_commands:
            if forbidden in clean:
                return (
                    RiskLevel.FORBIDDEN,
                    f"⛔ ENGELLENEN komut tespit edildi: {forbidden}"
                )

        # 2. SAFE — bilgi toplama
        safe_patterns = [
            r"^(df|du)\b",
            r"^free\b",
            r"^uptime\b",
            r"^top\s+-bn1",
            r"^ps\s+",
            r"^cat\s+/proc/",
            r"^uname\b",
            r"^hostname\b",
            r"^whoami\b",
            r"^id\b",
            r"^w\b",
            r"^last\b",
            r"^netstat\b",
            r"^ss\b",
            r"^ip\s+(addr|route|link)",
            r"^ping\b",
            r"^traceroute\b",
            r"^dig\b",
            r"^nslookup\b",
            r"^curl\b.*-s",
            r"^wget\b.*-q",
            r"^journalctl\b(?!.*--vacuum)",
            r"^systemctl\s+status\b",
            r"^systemctl\s+is-active\b",
            r"^tail\b",
            r"^head\b",
            r"^grep\b",
            r"^awk\b",
            r"^wc\b",
            r"^dmesg\b",
            r"^lsof\b",
            r"^vmstat\b",
            r"^iostat\b",
            r"^sar\b",
            r"^mpstat\b",
        ]
        for pattern in safe_patterns:
            if re.match(pattern, clean):
                return (RiskLevel.SAFE, "🟢 Bilgi toplama komutu")

        # 3. LOW risk — temizlik
        low_patterns = [
            r"^journalctl\s+--vacuum",
            r"^find\s+/tmp\b.*-delete",
            r"^apt\s+(list|search)",
            r"^yum\s+(list|search)",
        ]
        for pattern in low_patterns:
            if re.match(pattern, clean):
                return (RiskLevel.LOW, "🟡 Düşük riskli temizlik/bilgi komutu")

        # 4. MEDIUM risk — servis yönetimi (non-DB)
        medium_patterns = [
            r"^systemctl\s+(restart|stop|start)\s+(?!.*postgres|.*mysql|.*maria)",
            r"^service\s+\w+\s+(restart|stop|start)",
            r"^nginx\b",
        ]
        for pattern in medium_patterns:
            if re.match(pattern, clean):
                return (RiskLevel.MEDIUM, "🟠 Servis yönetimi komutu")

        # 5. HIGH risk — DB servis yönetimi, process kill
        high_patterns = [
            r"^systemctl\s+(restart|stop|start)\s+.*(postgres|mysql|maria)",
            r"^kill\b",
            r"^pkill\b",
            r"^killall\b",
        ]
        for pattern in high_patterns:
            if re.match(pattern, clean):
                return (RiskLevel.HIGH, "🔴 Veritabanı/process yönetimi")

        # 6. Bilinmeyen → HIGH (güvende kal)
        return (RiskLevel.HIGH, "🔴 Sınıflandırılamamış OS komutu — yüksek risk")

    def is_safe(self, command: str) -> bool:
        risk, _ = self.classify(command)
        return risk == RiskLevel.SAFE

    def is_forbidden(self, command: str) -> bool:
        risk, _ = self.classify(command)
        return risk == RiskLevel.FORBIDDEN
