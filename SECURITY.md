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
