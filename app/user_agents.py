"""Browser fingerprint presets. Each preset keeps UA + platform + GPU + screen
consistent with each other (consistency is what avoids naive bot flags)."""

PRESETS = {
    "win_chrome": {
        "label": "Windows / Chrome (Desktop)",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "platform": "Win32",
        "isMobile": False,
        "viewport": {"width": 1920, "height": 1080},
        "screen": {"width": 1920, "height": 1080, "availHeight": 1040},
        "cores": 8,
        "memory": 8,
        "gpuVendor": "Google Inc. (NVIDIA)",
        "gpuRenderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "locale": "en-US",
    },
    "mac_chrome": {
        "label": "macOS / Chrome (Desktop)",
        "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "isMobile": False,
        "viewport": {"width": 1512, "height": 982},
        "screen": {"width": 1512, "height": 982, "availHeight": 945},
        "cores": 8,
        "memory": 8,
        "gpuVendor": "Google Inc. (Apple)",
        "gpuRenderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1, Unspecified Version)",
        "locale": "en-US",
    },
    "win_edge": {
        "label": "Windows / Edge (Desktop)",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "platform": "Win32",
        "isMobile": False,
        "viewport": {"width": 1920, "height": 1080},
        "screen": {"width": 1920, "height": 1080, "availHeight": 1040},
        "cores": 12,
        "memory": 8,
        "gpuVendor": "Google Inc. (NVIDIA)",
        "gpuRenderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "locale": "en-US",
    },
    "iphone": {
        "label": "iPhone / Safari (Mobile)",
        "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
        "platform": "iPhone",
        "isMobile": True,
        "viewport": {"width": 393, "height": 852},
        "screen": {"width": 393, "height": 852, "availHeight": 852},
        "cores": 6,
        "memory": None,
        "gpuVendor": "Apple Inc.",
        "gpuRenderer": "Apple GPU",
        "locale": "en-US",
    },
    "android": {
        "label": "Android / Chrome (Mobile)",
        "userAgent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "platform": "Linux armv8l",
        "isMobile": True,
        "viewport": {"width": 412, "height": 915},
        "screen": {"width": 412, "height": 915, "availHeight": 915},
        "cores": 8,
        "memory": 8,
        "gpuVendor": "Google Inc. (Qualcomm)",
        "gpuRenderer": "ANGLE (Qualcomm, Adreno (TM) 740, OpenGL ES 3.2)",
        "locale": "en-US",
    },
}


def get_preset(preset_id: str) -> dict:
    return PRESETS.get(preset_id, PRESETS["win_chrome"])


def list_presets() -> list:
    return [{"id": k, **v} for k, v in PRESETS.items()]
