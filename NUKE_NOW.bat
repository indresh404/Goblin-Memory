@echo off
title GOBLIN'S MEMORY - NUKE LAUNCHER
color 0C

echo.
echo  ========================================================
echo       GOBLIN'S MEMORY - AUTOMATIC NUKE LAUNCHER
echo  ========================================================
echo.

cd /d d:\AI_Brain\Agent

echo  Launching automatic nuke sequence...
echo.

python nuke.py --force

echo.
echo  Nuke complete. Press any key to start Goblin's Memory...
pause > nul

python main.py
