"""Built-in browser for SafeProfiles ("SafeProfiles Browser").

Why: since Chrome 137, official (branded) Chrome IGNORES --load-extension, so
the fingerprint extension (timezone / canvas / GPU spoofing) silently never
loads and checkers see your real timezone. The fix is a private, unbranded
Chrome build that always accepts extensions.

We use Google's official **Chrome for Testing** builds (purpose-built for
automation, full Chrome engine, unbranded => extensions work). Downloaded
ONCE into the user's data folder - the app itself stays small and offline.

All code + downloads are plain and readable: version list from
googlechromelabs.github.io, zip from storage.googleapis.com.
"""
import shutil
import sys
import threading
import zipfile
from pathlib import Path

from . import net

LATEST_URL = ("https://googlechromelabs.github.io/chrome-for-testing/"
              "last-known-good-versions.json")

_state_lock = threading.Lock()
STATE = {"installing": False, "progress": 0.0, "error": "", "version": "",
         "path": ""}


# ---------------------------------------------------------------- locations
def root(data_dir) -> Path:
    return Path(data_dir) / "browser"


def _platform_dir() -> str:
    return "chrome-win64" if sys.platform == "win32" else "chrome-linux64"


def _platform_zip() -> str:
    return "win64" if sys.platform == "win32" else "linux64"


def builtin_exe(data_dir) -> Path | None:
    exe = root(data_dir) / _platform_dir() / ("chrome.exe" if sys.platform == "win32" else "chrome")
    try:
        if exe.is_file():
            return exe
    except OSError:
        pass
    return None


def builtin_version(data_dir) -> str | None:
    try:
        v = (root(data_dir) / "version.txt").read_text(encoding="utf-8").strip()
        return v or None
    except OSError:
        return None


# ---------------------------------------------------------------- status
def status(data_dir) -> dict:
    exe = builtin_exe(data_dir)
    with _state_lock:
        st = dict(STATE)
    st["installed"] = exe is not None
    st["platform"] = _platform_zip()
    if exe is not None:
        st["path"] = str(exe)
        st["version"] = builtin_version(data_dir) or ""
        st["installing"] = False
        st["progress"] = 100.0
        st["error"] = ""
    return st


# ---------------------------------------------------------------- download
def _latest_stable() -> str:
    import json
    import urllib.request
    req = urllib.request.Request(LATEST_URL, headers={"User-Agent": "SafeProfiles"})
    with net.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["channels"]["Stable"]["version"]


def _download(url: str, dest: Path, progress_cb=None) -> None:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "SafeProfiles"})
    with net.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 17)  # 128 KB
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb and total:
                    try:
                        progress_cb(done * 90.0 / total)  # 0-90% = download
                    except Exception:
                        pass
        tmp.replace(dest)


def _extract(zip_path: Path, dest: Path, progress_cb=None) -> None:
    with zipfile.ZipFile(zip_path) as z:
        members = z.infolist()
        for i, m in enumerate(members):
            z.extract(m, dest)
            if progress_cb:
                try:
                    progress_cb(90.0 + 10.0 * (i + 1) / max(1, len(members)))
                except Exception:
                    pass


def _install(data_dir) -> None:
    global STATE
    try:
        with _state_lock:
            STATE.update({"error": "", "progress": 0.0})
        data_dir = Path(data_dir)
        broot = root(data_dir)
        broot.mkdir(parents=True, exist_ok=True)
        version = _latest_stable()
        url = (f"https://storage.googleapis.com/chrome-for-testing-public/"
               f"{version}/{_platform_zip()}/{_platform_dir()}.zip")
        zpath = broot / "cft.zip"
        _download(url, zpath,
                  progress_cb=lambda p: _set(progress=p))
        # clean old copy, extract new one
        old = broot / _platform_dir()
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)
        _extract(zpath, broot, progress_cb=lambda p: _set(progress=p))
        zpath.unlink(missing_ok=True)
        (broot / "version.txt").write_text(version, encoding="utf-8")
        exe = builtin_exe(data_dir)
        if exe is None:
            raise RuntimeError("download finished but chrome binary not found")
        # linux: make executable
        if sys.platform != "win32":
            try:
                import os
                os.chmod(exe, 0o755)
            except OSError:
                pass
        with _state_lock:
            STATE.update({"version": version, "path": str(exe),
                          "progress": 100.0, "installing": False})
    except Exception as e:  # noqa: BLE001 - surface to the UI
        with _state_lock:
            STATE.update({"installing": False, "error": str(e)})


def _set(**kw) -> None:
    with _state_lock:
        STATE.update(kw)


def start_install(data_dir) -> bool:
    """Start installation in the background. Returns False if already running."""
    with _state_lock:
        if STATE["installing"]:
            return False
        STATE.update({"installing": True, "progress": 0.0, "error": ""})
    threading.Thread(target=_install, args=(data_dir,), daemon=True,
                     name="sp-browser-install").start()
    return True
