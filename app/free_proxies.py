"""Free proxy pool: fetch public lists, test them, keep the working ones.

Honest warning (also shown in the UI): free public proxies are run by
strangers. NEVER log into real Facebook/YouTube/Google accounts through one.
Use the pool for low-risk browsing/testing, and use direct connection (no
proxy) or your own trusted proxy for real logins.
"""
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import net
from .proxy_tools import test_proxy

SOURCES = {
    "http": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ],
    "socks4": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=8000&country=all",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    ],
    "socks5": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=8000&country=all",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    ],
}

LINE_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})\s*[:\s]\s*(\d{2,5})")


def fetch_lists(protocols: list | None = None, timeout: int = 20) -> dict:
    """Download raw proxy lists. Returns {protocol: [host:port, ...]}."""
    protocols = protocols or ["http", "socks5"]
    out: dict[str, list] = {}
    for proto in protocols:
        seen: set[str] = set()
        for url in SOURCES.get(proto, []):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SafeProfiles/1.0"})
                with net.urlopen(req, timeout=timeout) as r:
                    text = r.read().decode("utf-8", errors="ignore")
                for host, port in LINE_RE.findall(text):
                    if 1 <= int(port) <= 65535:
                        seen.add(f"{host}:{port}")
            except Exception:
                continue  # one dead source must not kill the fetch
        out[proto] = sorted(seen)
    return out


def test_many(candidates: list, timeout: int = 7, max_workers: int = 10,
              limit: int = 25, progress_cb=None) -> list:
    """Test candidates concurrently, return working ones sorted by latency."""
    candidates = candidates[:limit]
    working: list = []
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(test_proxy, c["protocol"], c["host"], c["port"], "", "", timeout): c
            for c in candidates
        }
        for fut in as_completed(future_map):
            done += 1
            if progress_cb:
                progress_cb(done, len(candidates))
            try:
                res = fut.result()
            except Exception:
                continue
            if res.get("success"):
                c = future_map[fut]
                working.append({
                    "protocol": c["protocol"],
                    "host": c["host"],
                    "port": c["port"],
                    "latencyMs": res.get("latencyMs"),
                    "country": res.get("country", ""),
                    "countryCode": res.get("countryCode", ""),
                    "city": res.get("city", ""),
                    "timezone": res.get("timezone", ""),
                    "checkedAt": int(time.time()),
                })
    working.sort(key=lambda x: x.get("latencyMs") or 99999)
    return working
