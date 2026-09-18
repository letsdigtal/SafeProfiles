"""Profile CRUD + data folders. Plain JSON you can inspect and back up."""
import json
import os
import secrets
import sys
from datetime import date
from pathlib import Path

from .secrets_store import SecretsStore
from .user_agents import get_preset


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        return base / "SafeProfiles"
    return Path.home() / ".safe-profiles"


def resource_path(*parts: str) -> Path:
    """Works both from source checkout and inside a PyInstaller onefile exe."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base).joinpath(*parts)


class ProfileStore:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir or default_data_dir())
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "browsers").mkdir(exist_ok=True)
        self.db_file = self.data_dir / "profiles.json"
        self.pool_file = self.data_dir / "proxy_pool.json"
        self.secrets = SecretsStore(self.data_dir)
        self._profiles: dict = {}
        self.load()
        if not self._profiles:
            self._create_starters()

    # ---------- persistence ----------
    def load(self):
        if self.db_file.exists():
            try:
                data = json.loads(self.db_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._profiles = data
            except (json.JSONDecodeError, OSError):
                self._profiles = {}

    def save(self):
        tmp = self.db_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._profiles, indent=2), encoding="utf-8")
        tmp.replace(self.db_file)

    # ---------- helpers ----------
    def _next_id(self) -> str:
        i = 1
        while f"profile_{i}" in self._profiles:
            i += 1
        return f"profile_{i}"

    def browser_dir(self, profile_id: str) -> Path:
        d = self.data_dir / "browsers" / profile_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _create_starters(self):
        self.create({
            "name": "Channel 1 - Desktop",
            "color": "#0ea5e9",
            "notes": "Main profile. Log in once, session stays isolated here.",
            "uaPreset": "win_chrome",
            "proxyMode": "none",
            "startUrl": "https://studio.youtube.com",
        })
        self.create({
            "name": "Page 1 - Mobile",
            "color": "#ec4899",
            "notes": "Mobile fingerprint profile.",
            "uaPreset": "android",
            "proxyMode": "none",
            "startUrl": "https://www.facebook.com",
        })

    # ---------- CRUD ----------
    def list(self, mask_secrets: bool = True) -> list:
        out = []
        for p in self._profiles.values():
            p = dict(p)
            if mask_secrets and "customProxy" in p and p["customProxy"].get("passwordEnc"):
                p["customProxy"] = dict(p["customProxy"])
                p["customProxy"]["passwordEnc"] = "***"
                p["customProxy"]["hasPassword"] = True
            out.append(p)
        return out

    def get(self, profile_id: str) -> dict | None:
        return self._profiles.get(profile_id)

    def create(self, fields: dict) -> dict:
        pid = self._next_id()
        preset = get_preset(fields.get("uaPreset", "win_chrome"))
        profile = {
            "id": pid,
            "name": fields.get("name", f"Profile {pid}"),
            "color": fields.get("color", "#22c55e"),
            "notes": fields.get("notes", ""),
            "browser": fields.get("browser", "auto"),
            "uaPreset": fields.get("uaPreset", "win_chrome"),
            "userAgent": fields.get("userAgent") or preset["userAgent"],
            "isMobile": fields.get("isMobile", preset["isMobile"]),
            "viewport": fields.get("viewport") or dict(preset["viewport"]),
            "locale": fields.get("locale", preset.get("locale", "en-US")),
            "timezone": fields.get("timezone", ""),
            "proxyMode": fields.get("proxyMode", "none"),  # none|custom|pool
            "customProxy": self._store_proxy_secret(fields.get("customProxy") or {}),
            "poolProxy": fields.get("poolProxy") or {},
            "startUrl": fields.get("startUrl", "about:blank"),
            "seed": secrets.token_hex(8),
            "createdAt": date.today().isoformat(),
        }
        self._profiles[pid] = profile
        self.browser_dir(pid)
        self.save()
        return profile

    def update(self, profile_id: str, fields: dict) -> dict | None:
        p = self._profiles.get(profile_id)
        if not p:
            return None
        for key in ("name", "color", "notes", "browser", "uaPreset", "userAgent",
                    "isMobile", "viewport", "locale", "timezone", "proxyMode",
                    "poolProxy", "startUrl"):
            if key in fields and fields[key] is not None:
                p[key] = fields[key]
        if "customProxy" in fields and fields["customProxy"] is not None:
            incoming = dict(fields["customProxy"])
            # "***" means "keep existing stored password"
            if incoming.get("passwordEnc") == "***":
                incoming["passwordEnc"] = p.get("customProxy", {}).get("passwordEnc", "")
            elif incoming.get("password"):
                incoming["passwordEnc"] = self.secrets.encrypt(incoming.pop("password"))
            p["customProxy"] = {
                "protocol": incoming.get("protocol", "http"),
                "host": incoming.get("host", ""),
                "port": incoming.get("port", ""),
                "username": incoming.get("username", ""),
                "passwordEnc": incoming.get("passwordEnc", ""),
            }
        if "newSeed" in fields and fields["newSeed"]:
            p["seed"] = secrets.token_hex(8)
        self.save()
        return p

    def delete(self, profile_id: str, delete_browser_data: bool = False) -> bool:
        if profile_id not in self._profiles:
            return False
        del self._profiles[profile_id]
        self.save()
        if delete_browser_data:
            import shutil
            shutil.rmtree(self.browser_dir(profile_id), ignore_errors=True)
        return True

    def _store_proxy_secret(self, proxy: dict) -> dict:
        return {
            "protocol": proxy.get("protocol", "http"),
            "host": proxy.get("host", ""),
            "port": proxy.get("port", ""),
            "username": proxy.get("username", ""),
            "passwordEnc": self.secrets.encrypt(proxy.get("password", "")) if proxy.get("password") else "",
        }

    def proxy_password(self, profile: dict) -> str:
        enc = (profile.get("customProxy") or {}).get("passwordEnc", "")
        if enc in ("", "***"):
            return ""
        return self.secrets.decrypt(enc)

    # ---------- free proxy pool ----------
    def load_pool(self) -> list:
        if self.pool_file.exists():
            try:
                data = json.loads(self.pool_file.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def save_pool(self, proxies: list):
        self.pool_file.write_text(json.dumps(proxies, indent=2), encoding="utf-8")
