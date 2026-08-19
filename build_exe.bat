@echo off
title Pandorix AutoClicker - Build
echo ============================================
echo   Pandorix AutoClicker - pravljenje .exe fajla
echo ============================================
echo.

echo [1/4] Instaliram potrebne biblioteke...
pip install -r requirements.txt
if errorlevel 1 (
    echo GRESKA: Instalacija biblioteka nije uspjela. Provjeri da li imas Python i pip instaliran.
    pause
    exit /b 1
)

echo.
echo [2/4] Provjeravam logo...
if exist logo.png (
    if not exist logo.ico (
        echo Pronasao sam logo.png, konvertujem u logo.ico...
        python convert_logo.py
    )
) else (
    echo Nisi stavio logo.png - .exe ce koristiti podrazumijevanu ikonu.
)

echo.
echo [3/4] Pravim .exe fajl (ovo moze potrajati minut-dva)...
if exist logo.ico (
    pyinstaller --noconfirm --onefile --windowed --icon=logo.ico --name "Pandorix AutoClicker" pandorix_autoclicker.py
) else (
    pyinstaller --noconfirm --onefile --windowed --name "Pandorix AutoClicker" pandorix_autoclicker.py
)

echo.
echo [4/4] Gotovo!
echo Tvoj .exe fajl se nalazi u folderu: dist\Pandorix AutoClicker.exe
echo.
pause
