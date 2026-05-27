@echo off
chcp 65001 >nul
echo ========================================
echo   PolygonToPintia - 打包为 .exe
echo ========================================
echo.

REM Find Python
set PYTHON=python
where %PYTHON% >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请确认 Python 已安装并添加到 PATH
    pause
    exit /b 1
)

echo [1/2] 清理旧构建...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [2/2] 使用 PyInstaller 打包...
"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --hidden-import tkinterdnd2 ^
    --name "PolygonToPintia" ^
    --distpath ./dist ^
    --workpath ./build ^
    --specpath ./build ^
    --clean ^
    main.py

if exist "dist\PolygonToPintia.exe" (
    echo.
    echo ========================================
    echo   打包成功！
    echo   输出: dist\PolygonToPintia.exe
    echo ========================================
) else (
    echo.
    echo [错误] 打包失败！
)
pause
