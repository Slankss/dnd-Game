@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

where claude >nul 2>&1
if errorlevel 1 (
  echo HATA: 'claude' komutu bulunamadi. Bu uygulama Claude Code CLI'ini kullanir.
  exit /b 1
)

call claude auth status 2>nul | findstr /C:"\"loggedIn\": true" >nul
if errorlevel 1 (
  echo HATA: Claude Code'a giris yapilmamis. Once sunu calistirin: claude auth login
  exit /b 1
)

if not exist ".venv" (
  echo Sanal ortam olusturuluyor...
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 (
      echo HATA: Sanal ortam olusturulamadi. Python kurulu mu?
      exit /b 1
    )
  )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo HATA: Sanal ortam etkinlestirilemedi.
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo HATA: Bagimliliklar kurulamadi.
  exit /b 1
)

if not defined PORT set "PORT=5050"
echo Sunucu basliyor: http://localhost:!PORT!
".venv\Scripts\python.exe" server.py
exit /b %errorlevel%
