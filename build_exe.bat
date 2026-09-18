@echo off
REM Build the single-file SafeProfiles.exe on Windows (run once).
REM Requires: Python 3.11+ from python.org (tick "Add python to PATH").
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller SafeProfiles.spec --noconfirm
echo.
echo DONE: dist\SafeProfiles.exe  - double-click it to run. No install needed.
pause
