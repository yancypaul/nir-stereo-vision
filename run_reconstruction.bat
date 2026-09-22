@echo off
chcp 65001 >nul
title Universal Stereo Reconstruction - One Click Run

echo ======================================================================
echo           通用工业级双目 3D 点云自动重建系统
echo           [正在使用 ICCV 2025 SOTA GREAT-Stereo 深度神经网络]
echo ======================================================================
echo.
F:\anaconda\envs\ffs\python.exe run_reconstruction.py --matcher great

echo.
echo ======================================================================
echo 重建完成！产物已归档至 data\output\hk_real_output\
echo 最新 3D 点云为: data\output\hk_real_output\latest_model.ply
echo ======================================================================
pause
