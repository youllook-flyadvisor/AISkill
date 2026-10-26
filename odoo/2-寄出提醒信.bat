@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo 找不到 Python，請先安裝 Python 3.10 以上：https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .env (echo 找不到 .env 設定檔，請看 docs\設定說明書.pdf & pause & exit /b 1)
python -m sales_reminder
if errorlevel 1 (echo. & echo 執行失敗，請看上面的訊息，或對照 docs\設定說明書.pdf 最後的「常見問題」。 & pause & exit /b 1)
echo.
pause
