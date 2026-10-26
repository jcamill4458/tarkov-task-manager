@echo off
rem Builds the app into dist\TarkovTaskManager\

python -m pip install pyinstaller
if errorlevel 1 goto failed

python -m PyInstaller --noconfirm --clean --noconsole --name TarkovTaskManager ^
    --add-data "assets/maps;assets/maps" ^
    --add-data "assets/mapConfig.json;assets" ^
    main.py
if errorlevel 1 goto failed

echo.
echo Done.
pause
exit /b 0

:failed
echo.
echo The build failed. Scroll up for the error.
pause
exit /b 1