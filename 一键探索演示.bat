@echo off
chcp 65001 >nul
title cpp-game-server-kit Explore Demo
echo Starting services and running the explore demo (about 10s)...
echo.
wsl -d Ubuntu-22.04 --cd "%~dp0" -- bash scripts/explore_demo.sh
echo.
echo Done. Press any key to close this window.
pause >nul
