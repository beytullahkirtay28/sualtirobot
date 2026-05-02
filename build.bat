@echo off
REM RUSUMAT 4 - Yuzey Istasyonu .exe Build Script (Windows)
REM Onkosul: Python 3.x kurulu olmali (https://python.org)

echo ============================================================
echo   RUSUMAT 4 - YUZEY ISTASYONU EXE BUILD
echo ============================================================
echo.

echo [1/4] Gerekli paketleri kontrol et / yukle...
python -m pip install --upgrade pip
python -m pip install pyinstaller pygame opencv-python pillow numpy pyserial
if errorlevel 1 (
    echo HATA: Paket kurulumu basarisiz. Internet baglantisi var mi?
    pause
    exit /b 1
)

echo.
echo [2/4] Eski build dosyalarini temizle...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Rusumat4.spec del Rusumat4.spec

echo.
echo [3/4] PyInstaller ile build (1-2 dakika surebilir)...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "Rusumat4" ^
    --noconfirm ^
    yuzey_istasyonu.py

if errorlevel 1 (
    echo HATA: Build basarisiz.
    pause
    exit /b 1
)

echo.
echo [4/4] Config dosyasini dist klasorune kopyala...
copy config.json dist\config.json

echo.
echo ============================================================
echo   BUILD TAMAM
echo ============================================================
echo.
echo Cikti: dist\Rusumat4.exe
echo        dist\config.json  (IP/port ayari icin duzenle)
echo.
echo dist klasorundeki bu iki dosyayi birlikte kopyala/dagit.
echo Python kurulu olmasi gerekmez, herhangi bir Windows'ta calisir.
echo.
pause
