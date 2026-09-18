"""Entry point: start the local server and open the dashboard.

Double-click behaviour (exe): a small console shows status, your default
browser opens the dashboard automatically. Close the console to quit.
Works fully offline - internet is only needed for actual web browsing.
"""
import argparse
import threading
import time
import webbrowser
from pathlib import Path

from . import __version__
from .server import AppServer


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SafeProfiles - multi-profile browser manager")
    ap.add_argument("--port", type=int, default=0, help="Local port (0 = auto-pick).")
    ap.add_argument("--data-dir", default=None, help="Profile data folder.")
    ap.add_argument("--no-browser", action="store_true", help="Don't auto-open the dashboard.")
    args = ap.parse_args(argv)

    server = AppServer(data_dir=Path(args.data_dir) if args.data_dir else None,
                       port=args.port).start()
    print("=" * 60, flush=True)
    print(f"  SafeProfiles v{__version__}  (open source, no telemetry)", flush=True)
    print(f"  Dashboard: {server.base_url}", flush=True)
    print(f"  Data folder: {server.store.data_dir}", flush=True)
    print("  Keep this window open. Press Ctrl+C to quit.", flush=True)
    if not args.port and server.port != 17500:
        print("", flush=True)
        print("  NOTE: port 17500 was busy - another SafeProfiles copy may", flush=True)
        print("  already be running. Close extra copies to avoid confusion,", flush=True)
        print(f"  and always use THIS window's URL: {server.base_url}", flush=True)
    print("=" * 60, flush=True)

    if not args.no_browser:
        def _open():
            time.sleep(0.6)
            try:
                webbrowser.open(server.base_url)
            except Exception as e:  # noqa: BLE001
                print(f"Could not auto-open browser: {e}")
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
