# Security policy

## Design guarantees

- **Open source, reproducible**: the exe is built from this exact code by a
  public GitHub Actions workflow (`.github/workflows/build-windows.yml`).
- **No telemetry, no accounts, no phone-home.** The app makes zero network
  requests except ones you explicitly trigger (proxy test / free-proxy fetch).
- **No auto-update.** You update by downloading a new release yourself.
- **Local server locked down**: binds `127.0.0.1` only, validates the Host
  header, requires a random per-run token for every API call, and sends no
  CORS headers (websites cannot reach it).
- **No remote-debugging flags** are ever passed to Chrome (no
  `--remote-debugging-port`, no `--remote-allow-origins`).
- **Proxy passwords encrypted** at rest (Fernet, key file with 0600 perms).

## Reporting a vulnerability

Open a GitHub issue titled `[SECURITY]` or contact the repo owner privately.
Please do not open public issues with exploit details before a fix exists.

## Optional: GitHub tunnel proxies (added in v1.1)

The dashboard can turn the user's own throwaway GitHub accounts into free
SOCKS5 proxies (Proxies tab). Design guarantees:

- The GitHub Personal Access Token is stored **encrypted** in the local data
  folder and is sent only to `api.github.com` over HTTPS — **never uploaded**
  anywhere else. The runner workflow only receives GitHub's own short-lived
  `GITHUB_TOKEN` scoped to the tunnel repo.
- The SOCKS5 endpoint requires a randomly generated username/password stored
  as encrypted GitHub Actions secrets (libsodium sealed box) — the tunnel is
  never an open proxy.
- Every file pushed to the user's GitHub account is plain text, generated from
  readable source in `app/gh_proxy.py` (`tunnel.yml` + `run_tunnel.sh`).

Clearly warned trade-offs (shown in the UI): the practice violates GitHub's
Terms of Service (ban risk — throwaway accounts only) and traffic transits
pinggy.io. The feature is strictly opt-in; the app works fully without it.
