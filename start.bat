@echo off
chcp 65001 >nul
echo ========================================
echo   AI 桌面宠物启动器
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\Activate.ps1" (
    echo [错误] 虚拟环境不存在！
    echo.
    echo 请先运行以下命令安装依赖：
    echo   python -m venv .venv
    echo   .\.venv\Scripts\Activate.ps1
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [信息] 激活虚拟环境...
call .venv\Scripts\Activate.ps1

echo [信息] 启动AI桌面宠物...
echo ========================================
echo.

python -m app.main

echo.
echo [信息] 程序已退出。
pause