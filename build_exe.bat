@echo off
REM 一键打包：生成单文件、无控制台的 dist\StoreApp.exe
REM 默认使用 conda evTest 环境；如需改用其他环境，修改下面的 PY 变量即可。
set PY=C:\Users\Chen\.conda\envs\evTest\python.exe

"%PY%" -m PyInstaller --noconfirm --onefile --windowed --name StoreApp main.py

if exist dist\StoreApp.exe (
    echo.
    echo 打包完成: dist\StoreApp.exe
) else (
    echo.
    echo 打包失败，请查看上方报错信息。
)
pause
