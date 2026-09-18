"""Local secret storage: proxy passwords are encrypted at rest with Fernet.

The key lives in the user's own data folder with 0600 permissions.
This protects against casual snooping/backups theft - it is NOT designed to
withstand malware already running as your user (nothing local can do that).
"""
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class SecretsStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.key_file = self.data_dir / ".key"
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self.key_file.exists():
            return self.key_file.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        try:
            os.chmod(self.key_file, 0o600)
        except OSError:
            pass  # Windows: best effort
        return key

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return ""
