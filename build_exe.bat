@echo off
setlocal

echo Installing/Updating PyInstaller...
python -m pip install --upgrade pyinstaller

echo.
echo Building LoliSwap.exe...
python -m PyInstaller --onefile --windowed --name LoliSwap loliswap_app.py

echo.
echo Done.
echo EXE file:
echo dist\LoliSwap.exe
pause
