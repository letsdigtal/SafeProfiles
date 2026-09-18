"""Local-only HTTP server for the SafeProfiles dashboard.

Security model (written to AVOID the flaws found in the audited app):
  * Binds 127.0.0.1 only - never reachable from the network.
  * Host header must be 127.0.0.1/localhost (blocks DNS-rebinding tricks).
  * Every /api/* call needs the random per-run token (X-App-Token header or
    ?token=). The token is generated fresh on each start and shown only in
    this app's own page - it dies when the app exits.
  * NO Access-Control-Allow-Origin header at all: random websites cannot read
    or call this API (browser same-origin policy blocks them).
  * No telemetry, no update checks, no remote config, no network calls except
    ones YOU trigger (proxy test / free-proxy fetch).
"""
import json
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import __version__
from .browser_runner import (find_browsers, is_running, launch, running_pids, stop)
from .free_proxies import fetch_lists, test_many
from .gh_proxy import GitHubError
from .profiles import ProfileStore, resource_path
from .proxy_tools import parse_proxy_string, test_proxy
from .user_agents import list_presets


class AppServer:
    def __init__(self, data_dir: Path | None = None, port: int = 0):
        self.store = ProfileStore(data_dir)
        self.token = secrets.token_urlsafe(24)
        self.httpd: ThreadingHTTPServer | None = None
        self.port = port

    def start(self):
        handler = self._make_handler()
        # Try a small range so the app "just opens" instead of port errors.
        candidates = [self.port] if self.port else list(range(17500, 17520))
        last_err: Exception | None = None
        for p in candidates:
            try:
                self.httpd = ThreadingHTTPServer(("127.0.0.1", p), handler)
                self.port = self.httpd.server_address[1]
                return self
            except OSError as e:
                last_err = e
        raise RuntimeError(f"No local port available (tried 17500-17519): {last_err}")

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}?token={self.token}"

    def serve_forever(self):
        assert self.httpd
        self.httpd.serve_forever()

    def shutdown(self):
        if self.httpd:
            self.httpd.shutdown()

    # ---------------- handler ----------------
    def _make_handler(self):
        store, token = self.store, self.token

        class Handler(BaseHTTPRequestHandler):
            server_version = "SafeProfiles/1.0"

            # -- helpers --
            def log_message(self, fmt, *args):  # quieter console
                pass

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").lower()
                return host.startswith("127.0.0.1") or host.startswith("localhost")

            def _authed(self, qs: dict) -> bool:
                if self.headers.get("X-App-Token") == token:
                    return True
                return qs.get("token", [""])[0] == token

            def _send_json(self, obj, status: int = 200):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                # NOTE: deliberately NO Access-Control-Allow-Origin header.
                self.end_headers()
                self.wfile.write(body)

            def _send_file(self, path: Path, ctype: str):
                try:
                    data = path.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                if path.name == "index.html":
                    data = data.replace(b"__APP_TOKEN__", token.encode())
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Connection", "close")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _read_json(self) -> dict:
                try:
                    length = int(self.headers.get("Content-Length", 0) or 0)
                except ValueError:
                    length = 0
                if length <= 0 or length > 1_000_000:
                    return {}
                try:
                    return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                except (ValueError, UnicodeDecodeError):
                    return {}

            # -- routing --
            def _route(self):
                if not self._host_ok():
                    return self._send_json({"ok": False, "error": "Forbidden host."}, 403)
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                method, path = self.command, parsed.path

                # Static UI (same-origin page; API still needs the token)
                if method == "GET" and path in ("/", "/index.html"):
                    return self._send_file(resource_path("static", "index.html"),
                                           "text/html; charset=utf-8")
                if method == "GET" and path == "/app.js":
                    return self._send_file(resource_path("static", "app.js"),
                                           "application/javascript; charset=utf-8")
                if method == "GET" and path == "/app.css":
                    return self._send_file(resource_path("static", "app.css"),
                                           "text/css; charset=utf-8")

                if not path.startswith("/api/"):
                    return self._send_json({"ok": False, "error": "Endpoint not found."}, 404)
                if not self._authed(qs):
                    return self._send_json({"ok": False, "error": "Missing or wrong app token."}, 401)

                # ---- API ----
                if path == "/api/status" and method == "GET":
                    return self._send_json({"ok": True, "version": __version__,
                                            "profiles": len(store.list()),
                                            "running": running_pids(),
                                            "dataDir": str(store.data_dir)})
                if path == "/api/browsers" and method == "GET":
                    return self._send_json({"ok": True, "browsers": find_browsers()})
                if path == "/api/user-agents" and method == "GET":
                    return self._send_json({"ok": True, "presets": list_presets()})

                if path == "/api/profiles" and method == "GET":
                    profiles = store.list()
                    for p in profiles:
                        p["running"] = is_running(p["id"])
                    return self._send_json({"ok": True, "profiles": profiles})
                if path == "/api/profiles" and method == "POST":
                    p = store.create(self._read_json())
                    return self._send_json({"ok": True, "profile": p})

                parts = path.strip("/").split("/")  # api, profiles, <id>, <action?>
                if len(parts) >= 3 and parts[0] == "api" and parts[1] == "profiles":
                    pid = parts[2]
                    if len(parts) == 3 and method == "GET":
                        p = store.get(pid)
                        if not p:
                            return self._send_json({"ok": False, "error": "Profile not found."}, 404)
                        return self._send_json({"ok": True, "profile": p})
                    if len(parts) == 3 and method == "PUT":
                        p = store.update(pid, self._read_json())
                        if not p:
                            return self._send_json({"ok": False, "error": "Profile not found."}, 404)
                        return self._send_json({"ok": True, "profile": p})
                    if len(parts) == 3 and method == "DELETE":
                        qs_del = parse_qs(urlparse(self.path).query)
                        ok = store.delete(pid, qs_del.get("wipe", ["0"])[0] == "1")
                        if not ok:
                            return self._send_json({"ok": False, "error": "Profile not found."}, 404)
                        return self._send_json({"ok": True})
                    if len(parts) == 4 and parts[3] == "launch" and method == "POST":
                        p = store.get(pid)
                        if not p:
                            return self._send_json({"ok": False, "error": "Profile not found."}, 404)
                        try:
                            browser_pid = launch(p, store.data_dir, store)
                        except RuntimeError as e:
                            return self._send_json({"ok": False, "error": str(e)})
                        except OSError as e:
                            return self._send_json({"ok": False, "error": f"Could not start browser: {e}"})
                        return self._send_json({"ok": True, "pid": browser_pid})
                    if len(parts) == 4 and parts[3] == "stop" and method == "POST":
                        return self._send_json({"ok": True, "stopped": stop(pid)})

                if path == "/api/proxy/parse" and method == "POST":
                    body = self._read_json()
                    try:
                        parsed_proxy = parse_proxy_string(body.get("raw", ""))
                    except ValueError as e:
                        return self._send_json({"ok": False, "error": str(e)})
                    return self._send_json({"ok": True, "proxy": parsed_proxy})

                if path == "/api/proxy/test" and method == "POST":
                    body = self._read_json()
                    if not body.get("host") or not body.get("port"):
                        return self._send_json({"ok": False, "error": "Proxy host/port required."})
                    res = test_proxy(body.get("protocol", "http"), body["host"],
                                     int(body["port"]), body.get("username", ""),
                                     body.get("password", ""),
                                     timeout=int(body.get("timeout", 10)))
                    return self._send_json({"ok": res.get("success", False), **res})

                if path == "/api/pool" and method == "GET":
                    return self._send_json({"ok": True, "pool": store.load_pool()})
                if path == "/api/pool/fetch" and method == "POST":
                    body = self._read_json()
                    lists = fetch_lists(body.get("protocols", ["http", "socks5"]))
                    total = sum(len(v) for v in lists.values())
                    # stash raw candidates server-side for the test step
                    self.server._pool_candidates = [  # type: ignore[attr-defined]
                        {"protocol": proto, "host": c.split(":")[0], "port": int(c.split(":")[1])}
                        for proto, items in lists.items() for c in items
                    ]
                    return self._send_json({"ok": True, "counts": {k: len(v) for k, v in lists.items()},
                                            "total": total})
                if path == "/api/pool/test" and method == "POST":
                    body = self._read_json()
                    candidates = getattr(self.server, "_pool_candidates", [])
                    if not candidates:
                        return self._send_json({"ok": False,
                                                "error": "Fetch the lists first (Step 1)."})
                    import random
                    random.shuffle(candidates)
                    working = test_many(candidates,
                                        timeout=int(body.get("timeout", 7)),
                                        limit=int(body.get("limit", 25)))
                    existing = {(p["host"], p["port"]): p for p in store.load_pool()}
                    for w in working:
                        existing[(w["host"], w["port"])] = w
                    merged = sorted(existing.values(), key=lambda x: x.get("latencyMs") or 99999)[:200]
                    store.save_pool(merged)
                    return self._send_json({"ok": True, "working": working,
                                            "tested": min(len(candidates), int(body.get("limit", 25))),
                                            "poolSize": len(merged)})
                if path == "/api/pool/clear" and method == "POST":
                    store.save_pool([])
                    return self._send_json({"ok": True})

                # ---- GitHub tunnel accounts (optional; user's own throwaway accounts) ----
                if path == "/api/gh/accounts" and method == "GET":
                    return self._send_json({"ok": True, "accounts": store.gh.list(refresh=True)})
                if path == "/api/gh/accounts" and method == "POST":
                    body = self._read_json()
                    try:
                        acc = store.gh.add(body.get("label", ""), body.get("token", ""))
                    except GitHubError as e:
                        return self._send_json({"ok": False, "error": str(e)}, 400)
                    return self._send_json({"ok": True, "account": acc})
                if (len(parts) >= 5 and parts[0] == "api" and parts[1] == "gh"
                        and parts[2] == "accounts"):
                    aid, action = parts[3], parts[4]
                    try:
                        if action == "start" and method == "POST":
                            return self._send_json({"ok": True, "account": store.gh.start(aid)})
                        if action == "stop" and method == "POST":
                            return self._send_json({"ok": True, "account": store.gh.stop(aid)})
                        if action == "refresh" and method == "POST":
                            return self._send_json({"ok": True, "account": store.gh.refresh(aid)})
                        if action == "test" and method == "POST":
                            return self._send_json({"ok": True, **store.gh.test(aid)})
                        if action == "remove" and method == "POST":
                            body = self._read_json()
                            return self._send_json(store.gh.remove(aid, wipe=bool(body.get("wipe"))))
                    except GitHubError as e:
                        return self._send_json({"ok": False, "error": str(e)}, 400)
                    except KeyError:
                        return self._send_json({"ok": False, "error": "Account not found."}, 404)

                return self._send_json({"ok": False, "error": "Endpoint not found."}, 404)

            def do_GET(self):
                self._route()

            def do_POST(self):
                self._route()

            def do_PUT(self):
                self._route()

            def do_DELETE(self):
                self._route()

            def do_OPTIONS(self):  # no CORS: refuse preflights
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()

        return Handler


def find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
