@echo off
cd /d "%~dp0\.."

echo Compilando launcher para Satisfactory...
pyinstaller --noconsole --onefile ^
    --name FactoryGameSteam ^
    --add-data "common;common" ^
    --hidden-import "pydantic" ^
    --hidden-import "common.models" ^
    client/launcher.py

echo.
if exist "dist\FactoryGameSteam.exe" (
    echo [EXITO] Binario generado en dist\FactoryGameSteam.exe
) else (
    echo [ERROR] Fallo la compilacion.
)
pause