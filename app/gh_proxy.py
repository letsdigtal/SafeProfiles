"""Optional: free SOCKS5 proxies powered by YOUR OWN GitHub accounts.

This replaces the dangerous "GitHub token proxy" of the audited app with a
fully readable version. How it works:

  1. You create a throwaway GitHub account and paste a Personal Access Token
     (classic, scopes: repo + workflow) into the dashboard.
  2. SafeProfiles creates a repo `<username>/safeprofiles-tunnel` in that
     account and uploads two plain-text files:
        .github/workflows/tunnel.yml   (the runner workflow)
        run_tunnel.sh                  (SOCKS5 server + tunnel keeper)
  3. The workflow runs `microsocks` (a tiny open-source SOCKS5 server) on
     GitHub's runner and exposes it through a pinggy.io TCP tunnel.
  4. The runner commits the public tunnel address to `endpoint.json`;
     SafeProfiles reads it and routes the profile through
     socks5://user:pass@<tunnel-address>.

Security differences vs. the audited app:
  * Your PAT is stored ENCRYPTED locally and NEVER uploaded anywhere. The
    runner only receives GitHub's own short-lived GITHUB_TOKEN.
  * The SOCKS5 proxy REQUIRES a random username/password (the audited app
    ran an OPEN proxy that anyone could find and abuse).
  * Every file in the tunnel repo is plain text - nothing base64-hidden.

⚠️ HONEST WARNING: running proxies on GitHub Actions is against GitHub's
Terms of Service. Only use throwaway accounts you can afford to lose.
Traffic passes through pinggy.io (a third party). For valuable logins
prefer a direct connection or a trusted custom proxy.
"""
import base64
import json
import secrets as _pysecrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import net

try:
    from nacl import encoding as nacl_encoding
    from nacl.public import PublicKey, SealedBox
    HAVE_NACL = True
except Exception:  # pragma: no cover - pynacl is in requirements.txt
    HAVE_NACL = False

API = "https://api.github.com"
REPO_NAME = "safeprofiles-tunnel"
REPO_DESC = "Created by SafeProfiles - personal SOCKS5 tunnel worker"

WORKFLOW_PATH = ".github/workflows/tunnel.yml"
SCRIPT_PATH = "run_tunnel.sh"

# ---------------------------------------------------------------------------
# Everything below runs on GitHub's servers - kept simple and readable.
# ---------------------------------------------------------------------------
WORKFLOW_YAML = """name: safeprofiles-tunnel
on:
  workflow_dispatch:
  schedule:
    - cron: "*/25 * * * *"
permissions:
  contents: write
  actions: read
concurrency:
  group: safeprofiles-tunnel
  cancel-in-progress: false
jobs:
  tunnel:
    runs-on: ubuntu-latest
    timeout-minutes: 335
    steps:
      - name: Skip if a tunnel run is already active
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          N=$(gh api "repos/$GITHUB_REPOSITORY/actions/workflows/tunnel.yml/runs?per_page=10" --jq '[.workflow_runs[] | select(.status == "in_progress")] | length')
          echo "in-progress tunnel runs: $N"
          if [ "$N" -gt 1 ]; then echo "Another run is already active - exiting."; exit 0; fi
      - uses: actions/checkout@v4
      - name: Install microsocks
        run: |
          sudo apt-get update -qq || true
          if ! sudo apt-get install -y -qq microsocks; then
            echo "apt install failed - building microsocks from source"
            sudo apt-get install -y -qq gcc make git || true
            rm -rf /tmp/ms && git clone --depth 1 https://github.com/rofl0r/microsocks /tmp/ms
            make -C /tmp/ms && sudo cp /tmp/ms/microsocks /usr/local/bin/
          fi
          command -v microsocks || { echo "microsocks unavailable"; exit 1; }
      - name: Start SOCKS5 server and keep tunnel alive
        env:
          SOCKS_USER: ${{ secrets.SOCKS_USER }}
          SOCKS_PASS: ${{ secrets.SOCKS_PASS }}
        run: bash run_tunnel.sh
"""

RUN_TUNNEL_SH = """#!/usr/bin/env bash
# SafeProfiles tunnel worker - plain text, nothing hidden.
# Runs a password-protected SOCKS5 server locally and exposes it via
# pinggy.io. Publishes the public address to endpoint.json in this repo.
set -u
[ -z "$SOCKS_USER" ] && { echo "SOCKS_USER secret missing"; exit 1; }
[ -z "$SOCKS_PASS" ] && { echo "SOCKS_PASS secret missing"; exit 1; }

EP_FILE="endpoint.json"
LAST=""

microsocks -i 127.0.0.1 -p 1080 "$SOCKS_USER" "$SOCKS_PASS" &
SOCKS_PID=$!
trap 'kill $SOCKS_PID 2>/dev/null' EXIT

git config user.name  "safeprofiles-bot" 2>/dev/null || true
git config user.email "safeprofiles-bot@users.noreply.github.com" 2>/dev/null || true

publish() {
  local addr="$1" host_port
  [ "$addr" = "$LAST" ] && return 0
  host_port="${addr#tcp://}"
  printf '{"endpoint":"%s","updated":"%s"}\\n' "$host_port" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EP_FILE"
  git add "$EP_FILE" 2>/dev/null || true
  git commit -qm "endpoint: $host_port" 2>/dev/null || true
  git pull --rebase -q 2>/dev/null || true
  if git push -q 2>/dev/null; then
    LAST="$addr"
    echo "published endpoint: $host_port"
  else
    LAST=""
    echo "WARN: push failed, will retry on next reconnect"
  fi
}

while kill -0 "$SOCKS_PID" 2>/dev/null; do
  rm -f tunnel.log
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \\
      -o ExitOnForwardFailure=yes -o ServerAliveInterval=25 -o ServerAliveCountMax=4 \\
      -p 443 -R 0:localhost:1080 tcp@a.pinggy.io >tunnel.log 2>&1 &
  SSH_PID=$!
  ADDR=""
  for _ in $(seq 1 25); do
    kill -0 "$SSH_PID" 2>/dev/null || break
    ADDR=$(grep -oE 'tcp://[A-Za-z0-9.-]+:[0-9]+' tunnel.log 2>/dev/null | head -n1)
    if [ -z "$ADDR" ]; then
      H=$(grep -oE '[A-Za-z0-9-]+\\.tcp\\.pinggy\\.io:[0-9]+' tunnel.log 2>/dev/null | head -n1)
      [ -n "$H" ] && ADDR="tcp://$H"
    fi
    [ -n "$ADDR" ] && break
    sleep 1
  done
  if [ -n "$ADDR" ]; then
    publish "$ADDR"
    wait "$SSH_PID" 2>/dev/null || true   # tunnel dropped -> reconnect
  else
    kill "$SSH_PID" 2>/dev/null || true
    sleep 20
  fi
done
echo "socks server exited"
"""


class GitHubError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# Thin GitHub REST client (stdlib only, no extra dependencies)
# ---------------------------------------------------------------------------
def _request(method: str, path: str, token: str, body: dict | None = None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "SafeProfiles")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with net.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except ValueError:
            parsed = {}
        msg = parsed.get("message") or f"GitHub API HTTP {e.code}"
        if e.code == 401:
            msg = ("GitHub rejected this token (401 Bad credentials). Common causes: "
                   "the token was deleted or revoked, it was copied incompletely, or "
                   "it no longer exists. Create a fresh CLASSIC token (tick repo + "
                   "workflow) and paste the whole ghp_... string.")
        elif e.code == 403 and "rate limit" in msg.lower():
            msg = "GitHub rate limit reached - wait a few minutes and retry."
        raise GitHubError(e.code, msg) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise GitHubError(0, f"Cannot reach github.com ({reason}). Check your internet "
                             "connection.") from None


def verify_token(token: str) -> dict:
    if token.startswith("github_pat_"):
        raise GitHubError(400,
            "That is a FINE-GRAINED token. SafeProfiles needs a CLASSIC token:\n"
            "GitHub -> Settings -> Developer settings -> Personal access tokens -> "
            "Tokens (classic) -> Generate new token -> tick repo + workflow.")
    _, user, headers = _request("GET", "/user", token)
    scopes = (headers.get("X-OAuth-Scopes") or headers.get("x-oauth-scopes") or "").strip()
    if scopes:  # classic tokens report their scopes; fine-grained do not
        granted = [x.strip() for x in scopes.split(",")]
        missing = [s for s in ("repo", "workflow") if s not in granted]
        if missing:
            raise GitHubError(403, "Token is missing scope(s): " + ", ".join(missing)
                              + ". Create a CLASSIC token and tick both 'repo' and 'workflow'.")
    if not user.get("login"):
        raise GitHubError(401, "GitHub did not return a username for this token.")
    return {"login": user["login"], "scopes": scopes}


def put_file(token: str, owner: str, repo: str, path: str, content: str, message: str):
    q = urllib.parse.quote(path, safe="/")
    sha = None
    try:
        _, data, _ = _request("GET", f"/repos/{owner}/{repo}/contents/{q}?ref=main", token)
        sha = data.get("sha")
    except GitHubError as e:
        if e.status != 404:
            raise
    body = {"message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": "main"}
    if sha:
        body["sha"] = sha
    _request("PUT", f"/repos/{owner}/{repo}/contents/{q}", token, body)


def ensure_repo(token: str, owner: str) -> dict:
    """Create the (public) tunnel repo if needed and upload the worker files."""
    created = False
    try:
        _request("GET", f"/repos/{owner}/{REPO_NAME}", token)
    except GitHubError as e:
        if e.status != 404:
            raise
        # Public on purpose: public repos get UNLIMITED free Actions minutes.
        # The SOCKS proxy is password-protected, so a public repo is still safe.
        # (Switch to private in GitHub settings if you prefer - but private
        # repos only include ~2000 free Actions minutes/month.)
        _request("POST", "/user/repos", token, {
            "name": REPO_NAME, "description": REPO_DESC, "private": False,
            "auto_init": True, "has_issues": False, "has_wiki": False,
            "has_projects": False,
        })
        created = True
        time.sleep(3)
    last_err: GitHubError | None = None
    for attempt in range(5):  # brand-new repos can 409 for a few seconds
        try:
            put_file(token, owner, REPO_NAME, WORKFLOW_PATH, WORKFLOW_YAML,
                     "SafeProfiles: tunnel workflow (readable, nothing hidden)")
            put_file(token, owner, REPO_NAME, SCRIPT_PATH, RUN_TUNNEL_SH,
                     "SafeProfiles: tunnel worker script")
            return {"repo": REPO_NAME, "created": created}
        except GitHubError as e:
            if e.status in (404, 409) and attempt < 4:
                last_err = e
                time.sleep(2.5)
                continue
            raise
    raise last_err or GitHubError(0, "Could not upload worker files.")


def set_secret(token: str, owner: str, repo: str, name: str, value: str):
    if not HAVE_NACL:
        raise GitHubError(-1, "PyNaCl is missing on this machine. "
                              "Run: pip install -r requirements.txt  (or use the .exe build).")
    _, pk, _ = _request("GET", f"/repos/{owner}/{repo}/actions/secrets/public-key", token)
    box = SealedBox(PublicKey(pk["key"].encode("ascii"), nacl_encoding.Base64Encoder()))
    encrypted = base64.b64encode(box.encrypt(value.encode("utf-8"))).decode("ascii")
    _request("PUT", f"/repos/{owner}/{repo}/actions/secrets/{name}", token,
             {"encrypted_value": encrypted, "key_id": pk["key_id"]})


def set_workflow_enabled(token: str, owner: str, repo: str, enabled: bool):
    for attempt in range(4):
        try:
            _request("PUT", f"/repos/{owner}/{repo}/actions/workflows/tunnel.yml/state", token,
                     {"state": "enabled" if enabled else "disabled"})
            return
        except GitHubError as e:
            if e.status == 404 and attempt < 3:
                time.sleep(4)  # brand-new repo: workflow not indexed yet
                continue
            if e.status == 404:
                return  # fresh workflows are enabled by default; nothing to do
            raise


def dispatch(token: str, owner: str, repo: str):
    for attempt in range(6):  # just-created workflows can take a minute to index
        try:
            _request("POST", f"/repos/{owner}/{repo}/actions/workflows/tunnel.yml/dispatches",
                     token, {"ref": "main"})
            return
        except GitHubError as e:
            if e.status in (404, 422) and attempt < 5:
                time.sleep(6)
                continue
            raise


def cancel_active_runs(token: str, owner: str, repo: str) -> int:
    _, data, _ = _request("GET",
                          f"/repos/{owner}/{repo}/actions/workflows/tunnel.yml/runs?per_page=30",
                          token)
    n = 0
    for run in data.get("workflow_runs", []):
        if run.get("status") in ("in_progress", "queued"):
            try:
                _request("POST", f"/repos/{owner}/{repo}/actions/runs/{run['id']}/cancel", token)
                n += 1
            except GitHubError:
                pass
    return n


def read_endpoint(token: str, owner: str, repo: str) -> dict:
    try:
        _, data, _ = _request("GET",
                              f"/repos/{owner}/{repo}/contents/endpoint.json?ref=main", token)
        raw = base64.b64decode(data.get("content", "") or "").decode("utf-8", "replace")
        obj = json.loads(raw)
        return {"endpoint": obj.get("endpoint", ""), "updated": obj.get("updated", "")}
    except GitHubError as e:
        if e.status == 404:
            return {"endpoint": "", "updated": ""}
        raise
    except ValueError:
        return {"endpoint": "", "updated": ""}


def has_active_run(token: str, owner: str, repo: str) -> bool:
    _, data, _ = _request("GET",
                          f"/repos/{owner}/{repo}/actions/workflows/tunnel.yml/runs?per_page=10",
                          token)
    return any(r.get("status") in ("in_progress", "queued")
               for r in data.get("workflow_runs", []))


# ---------------------------------------------------------------------------
# Optional token pre-fill: put a token in token.txt next to the exe (or in the
# working directory) and the dashboard loads it automatically. The file is
# deleted once the account is added. Nothing is ever baked into the exe/repo.
# ---------------------------------------------------------------------------
def prefill_token_path(data_dir: Path | None = None):
    import sys
    candidates = []
    if getattr(sys, "frozen", False):  # PyInstaller exe
        candidates.append(Path(sys.executable).parent / "token.txt")
    else:
        candidates.append(Path.cwd() / "token.txt")
        candidates.append(Path(__file__).resolve().parent.parent / "token.txt")
    if data_dir is not None:
        candidates.append(Path(data_dir) / "token.txt")
    for c in candidates:
        try:
            if c.is_file():
                t = c.read_text(encoding="utf-8", errors="ignore").strip()
                if len(t) >= 20:
                    return c, t
        except OSError:
            continue
    return None, ""


def consume_prefill_token(data_dir: Path | None = None):
    p, _ = prefill_token_path(data_dir)
    if p is not None:
        try:
            p.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Account storage (gh_accounts.json in the user's private data folder).
# Tokens + SOCKS passwords are encrypted with the local SecretsStore.
# ---------------------------------------------------------------------------
def _poll_endpoints_forever(tunnels: "GhTunnels") -> None:
    """Daemon: every ~90s refresh tunnel endpoints from raw.githubusercontent.com
    so relays can follow address changes without any user action."""
    import time as _time
    while True:
        _time.sleep(90)
        with tunnels._lock:
            accounts = list(tunnels._accounts)
        for a in accounts:
            try:
                ep = tunnels.endpoint_of(a["username"], a["repo"])
            except GitHubError:
                continue
            new_ep = ep.get("endpoint", "")
            if new_ep and new_ep != a.get("endpoint"):
                with tunnels._lock:
                    a["endpoint"] = new_ep
                    a["endpointUpdated"] = ep.get("updated", "")
                    tunnels._save()
                print(f"[tunnel] {a.get('label', a['username'])}: new address {new_ep}",
                      flush=True)


class GhTunnels:
    def __init__(self, store):
        self.store = store
        self.secrets = store.secrets
        self.file = store.data_dir / "gh_accounts.json"
        self._lock = threading.RLock()
        self._accounts: list[dict] = []
        self._load()
        # v1.2.5: keep tunnel endpoints fresh in the background so open
        # browsers follow address rotations (pinggy changes ~hourly).
        threading.Thread(target=_poll_endpoints_forever, args=(self,),
                         daemon=True, name="sp-endpoint-poller").start()

    # ---------- storage ----------
    def _load(self):
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._accounts = [a for a in data if isinstance(a, dict)]
            except (json.JSONDecodeError, OSError):
                self._accounts = []

    def _save(self):
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._accounts, indent=2), encoding="utf-8")
        tmp.replace(self.file)

    def endpoint_of(self, username: str, repo: str) -> dict:
        """Read endpoint.json via raw.githubusercontent.com (public repo, no token,
        no strict rate limits). Returns {endpoint, updated} or raises GitHubError."""
        url = f"https://raw.githubusercontent.com/{username}/{repo}/main/endpoint.json"
        req = urllib.request.Request(url, headers={"User-Agent": "SafeProfiles"})
        try:
            with net.urlopen(req, timeout=15) as r:
                obj = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"endpoint": "", "updated": ""}
            raise GitHubError(e.code, f"endpoint.json fetch failed: HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise GitHubError(0, f"endpoint.json fetch failed: {e}") from None
        return {"endpoint": obj.get("endpoint", ""), "updated": obj.get("updated", "")}

    def _find(self, account_id: str) -> dict:
        with self._lock:
            for a in self._accounts:
                if a.get("id") == account_id:
                    return a
        raise KeyError(account_id)

    def _public(self, a: dict) -> dict:
        return {k: v for k, v in a.items() if k not in ("tokenEnc", "socksPassEnc")}

    def token_for(self, a: dict) -> str:
        token = self.secrets.decrypt(a.get("tokenEnc", ""))
        if not token:
            raise GitHubError(401, "Saved token unreadable - remove and re-add this account.")
        return token

    def socks_password(self, a: dict) -> str:
        return self.secrets.decrypt(a.get("socksPassEnc", ""))

    def socks_password_by_id(self, account_id: str) -> str:
        return self.socks_password(self._find(account_id))

    # ---------- operations ----------
    def list(self, refresh: bool = False) -> list:
        if refresh:
            with self._lock:
                for a in self._accounts:
                    self._refresh_account(a, persist=False)
                self._save()
        with self._lock:
            return [self._public(a) for a in self._accounts]

    def get(self, account_id: str) -> dict:
        return self._public(self._find(account_id))

    def add(self, label: str, token: str) -> dict:
        token = (token or "").strip()
        if len(token) < 20:
            raise GitHubError(400, "That does not look like a GitHub token. "
                                   "See the steps under the add form / README.")
        info = verify_token(token)
        username = info["login"]
        setup = ensure_repo(token, username)
        socks_user = "sp" + _pysecrets.token_hex(4)
        socks_pass = _pysecrets.token_hex(10)
        set_secret(token, username, REPO_NAME, "SOCKS_USER", socks_user)
        set_secret(token, username, REPO_NAME, "SOCKS_PASS", socks_pass)
        with self._lock:
            i = 1
            while any(a.get("id") == f"gh_{i}" for a in self._accounts):
                i += 1
            acc = {
                "id": f"gh_{i}",
                "label": (label or "").strip() or f"Tunnel {i}",
                "username": username,
                "repo": REPO_NAME,
                "tokenEnc": self.secrets.encrypt(token),
                "socksUser": socks_user,
                "socksPassEnc": self.secrets.encrypt(socks_pass),
                "endpoint": "",
                "endpointUpdated": "",
                "status": "starting",
                "statusNote": "Account added - first tunnel is starting (~1-2 min).",
                "repoCreated": setup["created"],
                "added": datetime.now(timezone.utc).date().isoformat(),
            }
            self._accounts.append(acc)
            self._save()
        self.start(acc["id"])
        return self._public(acc)

    def start(self, account_id: str) -> dict:
        a = self._find(account_id)
        token = self.token_for(a)
        set_workflow_enabled(token, a["username"], a["repo"], True)
        try:
            # cancel any stale run so the fresh one uses current credentials
            cancel_active_runs(token, a["username"], a["repo"])
            time.sleep(6)  # let the cancel land before dispatching
        except GitHubError:
            pass  # nothing to cancel - dispatch anyway
        dispatch(token, a["username"], a["repo"])
        with self._lock:
            a["status"] = "starting"
            a["statusNote"] = "Dispatched just now - endpoint appears in ~1-2 min, then press Refresh."
            self._save()
        return self._public(a)

    def stop(self, account_id: str) -> dict:
        a = self._find(account_id)
        token = self.token_for(a)
        cancel_active_runs(token, a["username"], a["repo"])
        set_workflow_enabled(token, a["username"], a["repo"], False)  # stop the cron too
        with self._lock:
            a["status"] = "stopped"
            a["statusNote"] = "Stopped (cron disabled). Press Start to run again."
            a["endpoint"] = ""  # old address is dead
            self._save()
        return self._public(a)

    def refresh(self, account_id: str) -> dict:
        a = self._find(account_id)
        with self._lock:
            self._refresh_account(a, persist=True)
            return self._public(a)

    def _refresh_account(self, a: dict, persist: bool = True):
        try:
            token = self.token_for(a)
        except GitHubError as e:
            a["status"], a["statusNote"] = "error", str(e)
            if persist:
                with self._lock:
                    self._save()
            return
        try:
            ep = read_endpoint(token, a["username"], a["repo"])
            active = has_active_run(token, a["username"], a["repo"])
            a["endpoint"] = ep.get("endpoint", "")
            a["endpointUpdated"] = ep.get("updated", "")
            if not active:
                a["status"] = "stopped"
                a["statusNote"] = "No workflow run active. Press Start."
            elif not a["endpoint"]:
                a["status"] = "starting"
                a["statusNote"] = "Runner is up, waiting for the tunnel address (~1-2 min)."
            else:
                a["status"] = "active"
                a["statusNote"] = ""
        except GitHubError as e:
            a["status"], a["statusNote"] = "error", str(e)
        if persist:
            with self._lock:
                self._save()

    def test(self, account_id: str) -> dict:
        from .proxy_tools import test_proxy
        a = self._find(account_id)
        if not a.get("endpoint") or ":" not in a["endpoint"]:
            return {"success": False,
                    "error": "No endpoint yet - press Start, wait ~1-2 min, then Refresh."}
        host, port = a["endpoint"].rsplit(":", 1)
        return test_proxy("socks5", host, int(port), a.get("socksUser", ""),
                          self.socks_password(a), timeout=15)

    def remove(self, account_id: str, wipe: bool = False) -> dict:
        a = self._find(account_id)
        note = ""
        if wipe:
            try:
                token = self.token_for(a)
                _request("DELETE", f"/repos/{a['username']}/{a['repo']}", token)
                note = "tunnel repo deleted from GitHub"
            except GitHubError as e:
                note = (f"could not delete the repo automatically ({e}) - "
                        f"delete github.com/{a['username']}/{a['repo']} manually")
        with self._lock:
            self._accounts = [x for x in self._accounts if x.get("id") != account_id]
            self._save()
        return {"ok": True, "note": note}
