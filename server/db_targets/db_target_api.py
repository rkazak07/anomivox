"""
DB Targets — Veritabanı Bağlantı Yönetimi API

Settings UI'dan DBA Agent'ın bağlanacağı veritabanı
hedeflerini (PostgreSQL, MySQL) CRUD ile yönetir.
Bağlantı bilgileri configs/db_targets.json dosyasında saklanır.
"""
import os
import json
import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import Body, Header

logger = logging.getLogger("db_target_api")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "configs", "db_targets.json"
)


def _read_targets() -> list:
    """db_targets.json'dan mevcut bağlantıları oku."""
    if not os.path.exists(CONFIG_PATH):
        return []
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"DB targets read error: {e}")
        return []


def _write_targets(targets: list):
    """db_targets.json'a bağlantıları yaz."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(targets, f, indent=2, ensure_ascii=False)
    logger.info(f"DB targets saved ({len(targets)} targets)")


def _safe_target(t: dict) -> dict:
    """Password'ı gizleyerek frontend'e gönder."""
    safe = dict(t)
    if safe.get("password"):
        safe["password_set"] = True
        safe["password"] = ""
    else:
        safe["password_set"] = False
        safe["password"] = ""
    # SSH password da gizle
    if safe.get("ssh_password"):
        safe["ssh_password_set"] = True
        safe["ssh_password"] = ""
    else:
        safe["ssh_password_set"] = False
        safe["ssh_password"] = ""
    return safe


def _test_pg_connection(t: dict) -> dict:
    """PostgreSQL bağlantı testi."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=t.get("host", "localhost"),
            port=int(t.get("port", 5432)),
            user=t.get("user", ""),
            password=t.get("password", ""),
            dbname=t.get("dbname", "postgres"),
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.execute("SELECT current_database(), current_user, pg_size_pretty(pg_database_size(current_database()))")
        db_info = cur.fetchone()
        cur.close()
        conn.close()
        return {
            "ok": True,
            "version": version,
            "database": db_info[0],
            "user": db_info[1],
            "size": db_info[2],
        }
    except ImportError:
        return {"ok": False, "error": "psycopg2 not installed"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _test_mysql_connection(t: dict) -> dict:
    """MySQL bağlantı testi."""
    try:
        import pymysql
        conn = pymysql.connect(
            host=t.get("host", "localhost"),
            port=int(t.get("port", 3306)),
            user=t.get("user", ""),
            password=t.get("password", ""),
            database=t.get("dbname", ""),
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        cur.execute("SELECT DATABASE(), USER()")
        db_info = cur.fetchone()
        cur.close()
        conn.close()
        return {
            "ok": True,
            "version": version,
            "database": db_info[0],
            "user": db_info[1],
        }
    except ImportError:
        return {"ok": False, "error": "pymysql not installed"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _test_ssh_connection(t: dict) -> dict:
    """SSH bağlantı testi."""
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": t.get("ssh_host", ""),
            "port": int(t.get("ssh_port", 22)),
            "username": t.get("ssh_user", ""),
            "timeout": 10,
        }

        # Key dosyası veya password
        ssh_key = t.get("ssh_key_path", "").strip()
        ssh_password = t.get("ssh_password", "").strip()
        if ssh_key:
            from pathlib import Path
            key_path = Path(ssh_key).expanduser()
            if key_path.exists():
                connect_kwargs["key_filename"] = str(key_path)
            else:
                return {"ok": False, "error": f"SSH key dosyası bulunamadı: {ssh_key}"}
        elif ssh_password:
            connect_kwargs["password"] = ssh_password
        else:
            return {"ok": False, "error": "SSH key veya password gerekli"}

        client.connect(**connect_kwargs)

        # Temel OS bilgisi al
        stdin, stdout, stderr = client.exec_command("uname -a && uptime && df -h / | tail -1", timeout=10)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        error = stderr.read().decode("utf-8", errors="replace").strip()
        client.close()

        return {
            "ok": True,
            "output": output[:500],
            "error_output": error[:200] if error else "",
        }
    except ImportError:
        return {"ok": False, "error": "paramiko not installed. pip install paramiko"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


# ── API Endpoints ─────────────────────────────────────────

async def list_db_targets(
    authorization: Optional[str] = Header(None),
):
    """Tüm DB hedeflerini listele."""
    targets = _read_targets()
    safe = [_safe_target(t) for t in targets]
    return {"code": 200, "msg": "success", "data": safe}


async def add_db_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Yeni DB hedefi ekle."""
    try:
        required = ["name", "db_type", "host", "port", "user", "dbname"]
        for field in required:
            if not data.get(field):
                return {"code": 400, "msg": f"'{field}' alanı zorunludur"}

        targets = _read_targets()

        # Aynı isimde var mı?
        if any(t["name"] == data["name"] for t in targets):
            return {"code": 400, "msg": f"'{data['name']}' isimli bağlantı zaten var"}

        target = {
            "id": str(uuid.uuid4())[:8],
            "name": data["name"].strip(),
            "db_type": data["db_type"],  # postgresql / mysql
            "host": data["host"].strip(),
            "port": int(data["port"]),
            "user": data["user"].strip(),
            "password": data.get("password", ""),
            "dbname": data["dbname"].strip(),
            "is_primary": data.get("is_primary", False),
            # SSH / OS erişimi (opsiyonel)
            "ssh_enabled": bool(data.get("ssh_enabled", False)),
            "ssh_host": data.get("ssh_host", "").strip(),
            "ssh_port": int(data.get("ssh_port", 22)),
            "ssh_user": data.get("ssh_user", "").strip(),
            "ssh_password": data.get("ssh_password", ""),
            "ssh_key_path": data.get("ssh_key_path", "").strip(),
            "ssh_last_tested": None,
            "ssh_last_status": None,
            # Meta
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_tested": None,
            "last_status": None,
        }

        # is_primary ise diğerlerinin primary'sini kaldır
        if target["is_primary"]:
            for t in targets:
                t["is_primary"] = False

        targets.append(target)
        _write_targets(targets)

        return {"code": 200, "msg": f"'{target['name']}' bağlantısı eklendi", "data": _safe_target(target)}
    except Exception as e:
        return {"code": 500, "msg": f"Ekleme hatası: {str(e)[:200]}"}


async def update_db_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """DB hedefi güncelle."""
    try:
        target_id = data.get("id")
        if not target_id:
            return {"code": 400, "msg": "'id' alanı zorunludur"}

        targets = _read_targets()
        idx = next((i for i, t in enumerate(targets) if t["id"] == target_id), None)
        if idx is None:
            return {"code": 404, "msg": "Bağlantı bulunamadı"}

        t = targets[idx]
        for field in ["name", "db_type", "host", "port", "user", "dbname", "is_primary"]:
            if field in data:
                if field == "port":
                    t[field] = int(data[field])
                elif field == "is_primary":
                    t[field] = bool(data[field])
                else:
                    t[field] = str(data[field]).strip()

        # Şifre: boş gelirse mevcut değeri koru
        if data.get("password"):
            t["password"] = data["password"]

        # SSH alanları
        if "ssh_enabled" in data:
            t["ssh_enabled"] = bool(data["ssh_enabled"])
        for ssh_field in ["ssh_host", "ssh_user", "ssh_key_path"]:
            if ssh_field in data:
                t[ssh_field] = str(data[ssh_field]).strip()
        if "ssh_port" in data:
            t["ssh_port"] = int(data["ssh_port"])
        if data.get("ssh_password"):
            t["ssh_password"] = data["ssh_password"]

        # is_primary ise diğerlerini sıfırla
        if t.get("is_primary"):
            for i, other in enumerate(targets):
                if i != idx:
                    other["is_primary"] = False

        _write_targets(targets)
        return {"code": 200, "msg": f"'{t['name']}' bağlantısı güncellendi", "data": _safe_target(t)}
    except Exception as e:
        return {"code": 500, "msg": f"Güncelleme hatası: {str(e)[:200]}"}


async def delete_db_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """DB hedefi sil."""
    try:
        target_id = data.get("id")
        if not target_id:
            return {"code": 400, "msg": "'id' alanı zorunludur"}

        targets = _read_targets()
        new_targets = [t for t in targets if t["id"] != target_id]
        if len(new_targets) == len(targets):
            return {"code": 404, "msg": "Bağlantı bulunamadı"}

        _write_targets(new_targets)
        return {"code": 200, "msg": "Bağlantı silindi"}
    except Exception as e:
        return {"code": 500, "msg": f"Silme hatası: {str(e)[:200]}"}


async def test_db_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """DB bağlantısını test et.
    Kayıtlı bir target ID ile veya inline parametrelerle test yapabilir."""
    try:
        target_id = data.get("id")

        if target_id:
            # Mevcut target'ı bul
            targets = _read_targets()
            target = next((t for t in targets if t["id"] == target_id), None)
            if not target:
                return {"code": 404, "msg": "Bağlantı bulunamadı"}
        else:
            # Inline parametrelerle test
            target = {
                "db_type": data.get("db_type", "postgresql"),
                "host": data.get("host", ""),
                "port": data.get("port", 5432),
                "user": data.get("user", ""),
                "password": data.get("password", ""),
                "dbname": data.get("dbname", ""),
            }

        db_type = target.get("db_type", "postgresql")
        if db_type == "postgresql":
            result = _test_pg_connection(target)
        elif db_type == "mysql":
            result = _test_mysql_connection(target)
        else:
            return {"code": 400, "msg": f"Desteklenmeyen veritabanı tipi: {db_type}"}

        # Test sonucunu kaydet
        if target_id:
            targets = _read_targets()
            for t in targets:
                if t["id"] == target_id:
                    t["last_tested"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    t["last_status"] = "ok" if result["ok"] else "error"
                    break
            _write_targets(targets)

        if result["ok"]:
            return {"code": 200, "msg": "Bağlantı başarılı!", "data": result}
        else:
            return {"code": 400, "msg": f"Bağlantı hatası: {result['error']}", "data": result}

    except Exception as e:
        return {"code": 500, "msg": f"Test hatası: {str(e)[:200]}"}


async def set_primary_db_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """Bir DB hedefini primary olarak işaretle."""
    try:
        target_id = data.get("id")
        if not target_id:
            return {"code": 400, "msg": "'id' alanı zorunludur"}

        targets = _read_targets()
        found = False
        for t in targets:
            if t["id"] == target_id:
                t["is_primary"] = True
                found = True
            else:
                t["is_primary"] = False

        if not found:
            return {"code": 404, "msg": "Bağlantı bulunamadı"}

        _write_targets(targets)
        return {"code": 200, "msg": "Primary bağlantı güncellendi"}
    except Exception as e:
        return {"code": 500, "msg": f"Güncelleme hatası: {str(e)[:200]}"}


async def test_ssh_target(
    data: dict = Body(...),
    authorization: Optional[str] = Header(None),
):
    """SSH bağlantısını test et."""
    try:
        target_id = data.get("id")
        if not target_id:
            return {"code": 400, "msg": "'id' alanı zorunludur"}

        targets = _read_targets()
        target = next((t for t in targets if t["id"] == target_id), None)
        if not target:
            return {"code": 404, "msg": "Bağlantı bulunamadı"}

        if not target.get("ssh_enabled"):
            return {"code": 400, "msg": "Bu bağlantıda SSH aktif değil"}
        if not target.get("ssh_host"):
            return {"code": 400, "msg": "SSH host adresi boş"}

        result = _test_ssh_connection(target)

        # Sonucu kaydet
        for t in targets:
            if t["id"] == target_id:
                t["ssh_last_tested"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                t["ssh_last_status"] = "ok" if result["ok"] else "error"
                break
        _write_targets(targets)

        if result["ok"]:
            return {"code": 200, "msg": "SSH bağlantısı başarılı!", "data": result}
        else:
            return {"code": 400, "msg": f"SSH hatası: {result['error']}", "data": result}

    except Exception as e:
        return {"code": 500, "msg": f"SSH test hatası: {str(e)[:200]}"}
