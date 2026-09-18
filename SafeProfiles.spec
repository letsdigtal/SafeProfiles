# PyInstaller build spec: single-file Windows exe. Build with:  pyinstaller SafeProfiles.spec
# (or just double-click build_exe.bat). Output: dist/SafeProfiles.exe
block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('static', 'static'), ('extension', 'extension')],
    hiddenimports=['nacl', 'nacl.public', 'nacl.bindings', 'nacl.encoding'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SafeProfiles',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # console window shows status (easy troubleshooting); minimize it after start
    disable_windowed_traceback=False,
)
