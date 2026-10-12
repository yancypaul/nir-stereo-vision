@echo off
chcp 65001 >nul
title Universal Stereo Reconstruction - One Click Run

echo ======================================================================
echo           通用工业级双目 3D 点云自动重建系统
echo           [正在使用 ICCV 2025 SOTA GREAT-Stereo 深度神经网络]
echo ======================================================================
echo.

REM 优先尝试系统当前默认的 python，如果找不到再尝试特定开发机路径
where python >nul 2>nul
if %errorlevel% equ 0 (
    python run_reconstruction.py --matcher great
) else if exist "F:\anaconda\envs\ffs\python.exe" (
    F:\anaconda\envs\ffs\python.exe run_reconstruction.py --matcher great
) else (
    echo [错误] 未在系统环境变量中检测到 Python！
    echo 请先安装 Python (建议 3.10+) 并在安装时勾选 "Add Python to PATH"。
    echo 然后运行: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo 重建完成！产物已归档至 data\output\hk_real_output\
echo 最新 3D 点云为: data\output\hk_real_output\latest_model.ply
echo ======================================================================
pause
