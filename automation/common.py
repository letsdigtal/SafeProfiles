"""Shared helpers for SafeProfiles automation scripts.

Principles: official APIs first, human pacing, small daily limits, and the
human always clicks the final Publish button by default (use --auto-confirm
only for your own test accounts).
"""
import json
import os
import random
import sys
import time
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SafeProfiles"
    return Path.home() / ".safe-profiles"


def get_profile(identifier: str, data_dir: Path | None = None) -> dict:
    data_dir = Path(data_dir or default_data_dir())
    db = json.loads((data_dir / "profiles.json").read_text(encoding="utf-8"))
    if identifier in db:
        return db[identifier]
    for p in db.values():
        if p.get("name") == identifier:
            return p
    raise SystemExit(f"Profile '{identifier}' not found. Create it in the SafeProfiles dashboard first.")


def profile_browser_dir(profile: dict, data_dir: Path | None = None) -> Path:
    data_dir = Path(data_dir or default_data_dir())
    d = data_dir / "browsers" / profile["id"]
    if not d.exists():
        raise SystemExit("This profile was never launched. Launch it once from the dashboard, log in, then close it.")
    lock = d / "SingletonLock"
    if lock.exists():
        # Chromium holds this file while running - persistent context would fail.
        print("NOTE: this profile's browser seems to be running. Close it in the dashboard first,")
        print("      otherwise Playwright cannot attach to the same data folder.")
    return d


def human_sleep(a: float = 1.0, b: float = 3.0):
    time.sleep(random.uniform(a, b))


def type_human(page, selector: str, text: str, delay_ms: int = 60):
    page.click(selector)
    human_sleep(0.3, 0.8)
    page.keyboard.type(text, delay=delay_ms)
    human_sleep(0.4, 1.2)


def open_profile_context(pw, profile: dict, data_dir=None, headless=False, browser_path=None):
    """Open a Playwright persistent context reusing the profile's login session."""
    user_dir = profile_browser_dir(profile, data_dir)
    vp = profile.get("viewport") or {"width": 1280, "height": 800}
    kwargs = dict(
        user_data_dir=str(user_dir),
        headless=headless,
        viewport={"width": vp["width"], "height": vp["height"]},
        locale=(profile.get("locale") or "en-US").replace("_", "-"),
        user_agent=profile.get("userAgent"),
        args=["--disable-blink-features=AutomationControlled"],
    )
    if browser_path:
        kwargs["executable_path"] = browser_path
        return pw.chromium.launch_persistent_context(**kwargs)
    return pw.chromium.launch_persistent_context(**kwargs)


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        raise SystemExit("Playwright not installed. Run: pip install -r automation/requirements.txt")
    from playwright.sync_api import sync_playwright
    return sync_playwright
