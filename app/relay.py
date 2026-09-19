"""Local proxy relay: authenticated proxies for Chrome WITHOUT extensions.

Chrome 137+ (official branded builds) ignores --load-extension, so the old
"proxy auth extension" trick no longer works there. This relay listens on
127.0.0.1 as a NO-AUTH SOCKS5 server - Chrome connects to it - and forwards
every connection through the REAL upstream proxy (socks5/socks4/http) with
the credentials applied locally.

v1.2.5: supports DYNAMIC upstreams. Tunnel proxies (GitHub tunnels via
pinggy.io) change their public address roughly every hour. A relay created
with a `resolver` callable asks for the current address on every new
connection and re-resolves + retries when the cached address dies - so an
open browser window keeps working across address rotations, without restart.
A `preferred_port` makes the relay port stable per profile, so the browser
also survives an app restart.

Runs as daemon threads inside the SafeProfiles process; dies with it.
Source is fully readable - nothing hidden.
"""
import base64
import select
import socket
import threading

from .proxy_tools import _socks_handshake


class ProxyRelay:
    """start() it, then point Chrome at socks5://127.0.0.1:<relay.port>.

    Static upstream:  ProxyRelay("socks5", host, port, user, pass)
    Dynamic upstream: ProxyRelay("socks5", "", 0, user, pass,
                                 resolver=lambda: (host, port), preferred_port=17642)
    """

    def __init__(self, protocol: str, host: str = "", port: int = 0,
                 username: str = "", password: str = "",
                 resolver=None, preferred_port: int = 0):
        self.protocol = (protocol or "http").lower()
        self.host = host
        self.port_up = int(port or 0)
        self.username = username or ""
        self.password = password or ""
        self.resolver = resolver          # () -> (host, port), for tunnels
        self.preferred_port = int(preferred_port or 0)
        self.port = 0
        self._cached_upstream: tuple[str, int] | None = None
        self._srv: socket.socket | None = None

    # ---------------- lifecycle ----------------
    def start(self) -> "ProxyRelay":
        last_err: OSError | None = None
        # try the preferred (stable) port a few times - old connections from
        # a previous relay instance need a moment to fully close
        if self.preferred_port:
            ports = [self.preferred_port] * 3 + [0]
        else:
            ports = [0]
        for idx, p in enumerate(ports):
            if idx and p:
                import time as _t
                _t.sleep(0.6)
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", p))
                srv.listen(128)
                srv.settimeout(1.0)  # so stop() can interrupt the accept loop
                self._srv = srv
                self.port = srv.getsockname()[1]
                break
            except OSError as e:
                last_err = e
                try:
                    srv.close()
                except OSError:
                    pass
        if self._srv is None:
            raise last_err or OSError("could not bind relay port")
        threading.Thread(target=self._accept_loop, daemon=True,
                         name=f"sp-relay-{self.port}").start()
        return self

    def stop(self):
        srv, self._srv = self._srv, None
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass

    def _accept_loop(self):
        while self._srv is not None:
            try:
                client, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # server socket closed -> shutting down
            threading.Thread(target=self._serve, args=(client,),
                             daemon=True).start()

    # ---------------- SOCKS5 server side (no auth, localhost only) ----------------
    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("connection closed early")
            buf += chunk
        return buf

    def _serve(self, client: socket.socket):
        upstream: socket.socket | None = None
        try:
            client.settimeout(90)
            ver, nmethods = self._recv_exact(client, 2)
            if ver != 5:
                return
            methods = self._recv_exact(client, nmethods)
            if 0 not in methods:
                try:
                    client.sendall(b"\x05\xff")  # no acceptable auth method
                except OSError:
                    pass
                return
            client.sendall(b"\x05\x00")  # choose NO-AUTH (we are localhost)
            ver, cmd, _rsv, atyp = self._recv_exact(client, 4)
            if cmd != 1:  # only CONNECT is supported
                client.sendall(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
                return
            if atyp == 1:
                target = socket.inet_ntoa(self._recv_exact(client, 4))
            elif atyp == 3:
                ln = self._recv_exact(client, 1)[0]
                target = self._recv_exact(client, ln).decode("utf-8", "replace")
            elif atyp == 4:
                target = socket.inet_ntop(socket.AF_INET6, self._recv_exact(client, 16))
            else:
                client.sendall(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
                return
            target_port = int.from_bytes(self._recv_exact(client, 2), "big")
            upstream = self._connect_upstream(target, target_port)
            client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            self._pump(client, upstream)
        except Exception:
            try:
                client.sendall(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            except Exception:
                pass
        finally:
            for s in (client, upstream):
                if s is not None:
                    try:
                        s.close()
                    except OSError:
                        pass

    # ---------------- upstream side (the real proxy, with credentials) ----------------
    def _current_upstream(self, refresh: bool = False) -> tuple[str, int]:
        if self.resolver is None:
            return self.host, self.port_up
        if refresh or self._cached_upstream is None:
            h, p = self.resolver()
            self._cached_upstream = (str(h), int(p))
        return self._cached_upstream

    def _connect_upstream(self, target_host: str, target_port: int) -> socket.socket:
        # With a resolver: if the cached (possibly dead) address fails,
        # re-resolve once and retry - this is what keeps an open browser
        # alive across tunnel address rotations.
        attempts = 2 if self.resolver is not None else 1
        last_err: Exception | None = None
        for attempt in range(attempts):
            try:
                uh, up = self._current_upstream(refresh=(attempt > 0))
                s = socket.create_connection((uh, up), timeout=20)
                try:
                    s.settimeout(20)
                    if self.protocol in ("socks4", "socks5"):
                        err = _socks_handshake(s, self.protocol, self.username,
                                               self.password, target_host, target_port)
                        if err:
                            raise ConnectionError(err)
                    else:  # http / https upstream -> CONNECT tunnel
                        req = (f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
                               f"Host: {target_host}:{target_port}\r\n")
                        if self.username:
                            creds = base64.b64encode(
                                f"{self.username}:{self.password}".encode()).decode()
                            req += f"Proxy-Authorization: Basic {creds}\r\n"
                        req += "\r\n"
                        s.sendall(req.encode())
                        head = b""
                        while b"\r\n\r\n" not in head and len(head) < 8192:
                            chunk = s.recv(4096)
                            if not chunk:
                                raise ConnectionError("proxy closed during CONNECT")
                            head += chunk
                        status = head.split(b"\r\n", 1)[0].decode("utf-8", "replace")
                        if " 200 " not in status + " ":
                            raise ConnectionError(f"proxy refused CONNECT: {status}")
                    s.settimeout(None)
                    return s
                except Exception:
                    try:
                        s.close()
                    except OSError:
                        pass
                    raise
            except Exception as e:  # noqa: BLE001 - retry with fresh address
                last_err = e
                continue
        raise ConnectionError(f"upstream proxy unreachable: {last_err}")

    # ---------------- bidirectional pipe ----------------
    @staticmethod
    def _pump(a: socket.socket, b: socket.socket):
        a.settimeout(None)
        b.settimeout(None)
        pair = [a, b]
        while True:
            try:
                r, _w, x = select.select(pair, [], pair, 600)
            except (OSError, ValueError):
                return
            if x or not r:
                return  # socket error or 10 minutes idle
            for s in r:
                try:
                    data = s.recv(65536)
                except OSError:
                    return
                if not data:
                    return
                out = b if s is a else a
                try:
                    out.sendall(data)
                except OSError:
                    return
