"""Shared HTTPS helper.

The PyInstaller onefile exe cannot always find Windows/system CA
certificates, which made every GitHub / proxy-list request fail with
"certificate verify failed" inside the exe (while working fine from
source). Using certifi's bundled CA store fixes that everywhere.
"""
import ssl
import urllib.request

try:
    import certifi
    _CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - certifi is in requirements.txt
    _CONTEXT = None


def ssl_context():
    """SSL context with certifi CAs (or None to use Python defaults)."""
    return _CONTEXT


def build_opener(*handlers):
    if _CONTEXT is not None:
        return urllib.request.build_opener(urllib.request.HTTPSHandler(context=_CONTEXT),
                                           *handlers)
    return urllib.request.build_opener(*handlers)


_OPENER = build_opener()


def urlopen(req, timeout=30):
    """Drop-in replacement for urllib.request.urlopen with working CAs."""
    return _OPENER.open(req, timeout=timeout)
