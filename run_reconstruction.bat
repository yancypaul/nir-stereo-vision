@echo off
chcp 65001 >nul
title Universal Stereo Reconstruction - One Click Run

echo ======================================================================
echo           通用工业级双目 3D 点云自动重建系统
echo ======================================================================
echo 请选择立体匹配算法:
echo   [1] 经典 SGBM-HH 算法 (极速轻量，保留清晰机柜边缘)
echo   [2] ICCV 2025 GREAT-Stereo 深度算法 (100%% 满覆盖，弱纹理白墙极平滑)
echo ======================================================================
set /p choice="请输入数字并按回车 [默认 1]: "

if "%choice%"=="2" (
    echo.
    echo [正在使用 GREAT-Stereo 深度神经网络计算...]
    F:\anaconda\envs\ffs\python.exe run_reconstruction.py --matcher great
) else (
    echo.
    echo [正在使用 SGBM-HH + WLS 算法计算...]
    F:\anaconda\envs\ffs\python.exe run_reconstruction.py --matcher sgbm
)

echo.
echo ======================================================================
echo 重建完成！产物已归档至 data\output\hk_real_output\
echo 最新 3D 点云为: data\output\hk_real_output\latest_model.ply
echo ======================================================================
pause

