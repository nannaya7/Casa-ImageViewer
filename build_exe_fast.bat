@echo off
setlocal

cd /d "%~dp0"

set "APP_NAME=PyImageViewer"
set "ENTRY=main.py"
set "PYTHON=python"
set "OUT_DIR=exe"
set "IMAGE_DIR=%~dp0image"
set "ICON_FILE=%~dp0image\icon\Casa-ImageViewer-ICON.ico"
set "LOG_FILE=%OUT_DIR%\build_fast.log"

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
echo Fast build started: %date% %time% > "%LOG_FILE%"

echo [1/4] Installing project requirements...
echo [1/4] Installing project requirements... >> "%LOG_FILE%"
%PYTHON% -m pip install -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

echo [2/4] Checking PyInstaller...
echo [2/4] Checking PyInstaller... >> "%LOG_FILE%"
%PYTHON% -m PyInstaller --version >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed. Installing...
    echo PyInstaller is not installed. Installing... >> "%LOG_FILE%"
    %PYTHON% -m pip install pyinstaller >> "%LOG_FILE%" 2>&1
    if errorlevel 1 goto :error
)

echo [3/4] Building fast-start onedir package...
echo [3/4] Building fast-start onedir package... >> "%LOG_FILE%"
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "%APP_NAME%" ^
    --distpath "%OUT_DIR%\dist_fast" ^
    --workpath "%OUT_DIR%\build_fast" ^
    --specpath "%OUT_DIR%" ^
    --icon "%ICON_FILE%" ^
    --add-data "%IMAGE_DIR%;image" ^
    --collect-all PIL ^
    --collect-all pillow_heif ^
    --collect-all rawpy ^
    --collect-all pypdfium2 ^
    --collect-all ezdxf ^
    --collect-all trimesh ^
    --collect-submodules OpenGL ^
    --collect-all OCP ^
    --hidden-import ui.image_viewer ^
    --hidden-import ui.cad_viewer ^
    --hidden-import ui.model3d_viewer ^
    --hidden-import loaders.image_loader ^
    --hidden-import loaders.dxf_loader ^
    --hidden-import loaders.stl_loader ^
    --hidden-import loaders.step_loader ^
    --hidden-import ezdxf.addons.odafc ^
    --hidden-import PyQt6.QtOpenGLWidgets ^
    --hidden-import PyQt6.QtSvg ^
    --exclude-module PyQt5 ^
    --exclude-module PySide2 ^
    --exclude-module PySide6 ^
    --exclude-module cadquery ^
    --exclude-module matplotlib ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module IPython ^
    --exclude-module pytest ^
    --exclude-module tkinter ^
    --exclude-module OpenGL.Tk ^
    "%ENTRY%" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :error

echo [4/4] Done.
echo [4/4] Done. >> "%LOG_FILE%"
echo Output: "%~dp0%OUT_DIR%\dist_fast\%APP_NAME%\%APP_NAME%.exe"
echo Output: "%~dp0%OUT_DIR%\dist_fast\%APP_NAME%\%APP_NAME%.exe" >> "%LOG_FILE%"
echo Log: "%~dp0%LOG_FILE%"
pause
exit /b 0

:error
echo.
echo [Error] Fast build failed.
echo [Error] Fast build failed. >> "%LOG_FILE%"
echo Log: "%~dp0%LOG_FILE%"
pause
exit /b 1
