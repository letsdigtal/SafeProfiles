"""SafeProfiles launcher (works from source AND as a PyInstaller exe)."""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
