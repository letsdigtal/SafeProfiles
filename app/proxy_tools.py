"""Proxy parsing + live testing. Raw sockets only, zero dependencies.

Supported input formats (same as ixBrowser/AdsPower):
  ip:port   ip:port:user:pass   user:pass@ip:port
  ip:port@user:pass   protocol://...   protocol://ip:port:user:pass
"""
import base64
import json
import re
import socket
import time

PROTO_RE = re.compile(r"^([a-zA-Z0-9]+)://")


def parse_proxy_string(raw: str) -> dict:
    s = (raw or "").strip()
    if not s:
        raise ValueError("Empty proxy string")
    protocol = "http"
    m = PROTO_RE.match(s)
    if m:
        protocol = m.group(1).lower()
        s = s[m.end():]
    if protocol not in ("http", "https", "socks4", "socks5"):
        protocol = "http"

    username = password = ""
    # user:pass@host...  OR  host...@user:pass
    if "@" in s:
        left, right = s.rsplit("@", 1) if s.count("@") == 1 else (None, None)
        if left is None:
            left, right = s.split("@", 1)[0], s.split("@", 1)[1]
        # decide which side is host:port (contains ':' + numeric port or '.' )
        if _looks_like_hostport(left):
            hostport, userinfo = left, right
        else:
            userinfo, hostport = left, right
        if ":" in userinfo:
            username, password = userinfo.split(":", 1)
        else:
            username = userinfo
        s = hostport

    parts = s.split(":")
    if len(parts) == 2:
        host, port = parts
    elif len(parts) == 4:
        # ip:port:user:pass
        host, port, username, password = parts
    elif len(parts) == 3 and parts[2].isdigit():
        host, port = f"{parts[0]}:{parts[1]}", parts[2]
    else:
        raise ValueError(f"Could not parse proxy format: {raw!r}")
    host = host.strip()
    try:
        port_i = int(str(port).strip())
    except ValueError:
        raise ValueError(f"Invalid port in: {raw!r}")
    if not host or not (1 <= port_i <= 65535):
        raise ValueError(f"Invalid host/port in: {raw!r}")
    return {
        "protocol": protocol,
        "host": host,
        "port": port_i,
        "username": username.strip(),
        "password": password,
    }


def _looks_like_hostport(s: str) -> bool:
    s = s.strip()
    if ":" not in s:
        return False
    host, _, port = s.rpartition(":")
    return bool(host) and port.strip().isdigit()


def format_for_chrome(proxy: dict) -> str:
    """Builds --proxy-server value (Chrome takes no inline credentials)."""
    proto = (proxy.get("protocol") or "http").lower()
    scheme = {"http": "http", "https": "https", "socks4": "socks4", "socks5": "socks5"}.get(proto, "http")
    return f"{scheme}://{proxy['host']}:{proxy['port']}"


def test_proxy(protocol: str, host: str, port: int, username: str = "",
               password: str = "", timeout: int = 10) -> dict:
    """Connect through the proxy to ip-api.com and return geo/latency info."""
    protocol = (protocol or "http").lower()
    if protocol not in ("http", "https", "socks4", "socks5"):
        return {"success": False, "error": f"Unsupported protocol: {protocol}"}
    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        if protocol in ("socks4", "socks5"):
            err = _socks_handshake(sock, protocol, username, password, "ip-api.com", 80)
            if err:
                return {"success": False, "error": err}
            req = ("GET /json HTTP/1.1\r\nHost: ip-api.com\r\n"
                   "User-Agent: SafeProfiles-ProxyTest/1.0\r\nConnection: close\r\n\r\n")
        else:
            auth = ""
            if username:
                creds = base64.b64encode(f"{username}:{password}".encode()).decode()
                auth = f"Proxy-Authorization: Basic {creds}\r\n"
            req = ("GET http://ip-api.com/json HTTP/1.1\r\nHost: ip-api.com\r\n"
                   f"User-Agent: SafeProfiles-ProxyTest/1.0\r\n{auth}Connection: close\r\n\r\n")
        sock.sendall(req.encode())
        raw = b""
        while True:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break  # brief idle after data - we have what we need
            if not chunk:
                break
            raw += chunk
            # Stop once the body is complete (Content-Length). Some servers
            # keep the connection open, and waiting for EOF would falsely
            # look like a timeout (v1.2.6 fix).
            if b"\r\n\r\n" in raw:
                head, _, body = raw.partition(b"\r\n\r\n")
                m = re.search(rb"Content-Length:\s*(\d+)", head, re.IGNORECASE)
                if m and len(body) >= int(m.group(1)):
                    break
                sock.settimeout(2.5)  # got data; only wait briefly for more
        latency = int((time.time() - start) * 1000)
        text = raw.decode("utf-8", errors="ignore")
        if "407" in text.split("\r\n", 1)[0]:
            return {"success": False, "error": "407 Proxy Authentication Required - check username/password."}
        body = text.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in text else ""
        try:
            info = json.loads(body[body.find("{"):body.rfind("}") + 1])
        except (ValueError, IndexError):
            return {"success": False, "error": "Proxy connected but target returned non-JSON response."}
        return {
            "success": True,
            "latencyMs": latency,
            "ip": info.get("query", ""),
            "country": info.get("country", "Unknown"),
            "countryCode": info.get("countryCode", ""),
            "city": info.get("city", ""),
            "region": info.get("regionName", ""),
            "timezone": info.get("timezone", ""),
            "isp": info.get("isp", ""),
        }
    except socket.timeout:
        return {"success": False, "error": f"Connection timed out ({timeout}s). Host/port not responding."}
    except ConnectionRefusedError:
        return {"success": False, "error": "Connection refused. Proxy port is closed or offline."}
    except OSError as e:
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:  # noqa: BLE001 - surface as test failure
        return {"success": False, "error": f"Test failed: {e}"}
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _socks_handshake(sock: socket.socket, protocol: str, username: str,
                     password: str, target_host: str, target_port: int) -> str | None:
    if protocol == "socks5":
        if username:
            sock.sendall(b"\x05\x02\x00\x02")  # no-auth + user/pass
        else:
            sock.sendall(b"\x05\x01\x00")
        resp = sock.recv(2)
        if len(resp) < 2 or resp[0] != 5:
            return "Invalid SOCKS5 greeting response."
        if resp[1] == 2:
            if not username:
                return "SOCKS5 proxy requires authentication (username & password)."
            u, p = username.encode(), password.encode()
            sock.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            auth = sock.recv(2)
            if len(auth) < 2 or auth[1] != 0:
                return "SOCKS5 authentication failed (invalid username or password)."
        elif resp[1] != 0:
            return "SOCKS5 proxy rejected the connection method."
        host_b = target_host.encode()
        req = b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b + target_port.to_bytes(2, "big")
        sock.sendall(req)
        conn = sock.recv(10)
        if len(conn) < 2 or conn[1] != 0:
            return f"SOCKS5 proxy could not reach target (error code {conn[1] if len(conn) > 1 else '?'})."
        return None
    # socks4 (no auth)
    try:
        ip_bytes = socket.inet_aton(socket.gethostbyname(target_host))
    except OSError:
        return "SOCKS4: could not resolve target host."
    sock.sendall(b"\x04\x01" + target_port.to_bytes(2, "big") + ip_bytes + b"\x00")
    resp = sock.recv(8)
    if len(resp) < 2 or resp[1] != 0x5A:
        return "SOCKS4 proxy rejected the connection."
    return None
