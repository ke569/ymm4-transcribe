@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==================================================
echo   Transcription System (single-speaker, SRT only)
echo ==================================================
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] venv not found:
    echo   %VENV_PY%
    echo Please run setup.ps1 first ^(PowerShell -ExecutionPolicy Bypass -File .\setup.ps1^).
    pause
    exit /b 1
)

if not exist "%~dp0input\" (
    mkdir "%~dp0input"
    echo Created input\ folder. Put audio files there and run again.
    pause
    exit /b 0
)

if not exist "%~dp0output\" mkdir "%~dp0output"

set count=0
set errcount=0

for %%F in ("%~dp0input\*.wav" "%~dp0input\*.mp3" "%~dp0input\*.m4a" "%~dp0input\*.mp4" "%~dp0input\*.flac" "%~dp0input\*.ogg") do (
    if exist "%%~F" (
        set /a count+=1
        echo.
        echo === [!count!] %%~nxF ===
        "%VENV_PY%" -m ymm4_transcribe "%%~F" -o "%~dp0output\%%~nF.csv" --srt "%~dp0output\%%~nF.srt" --no-csv
        if errorlevel 1 (
            set /a errcount+=1
            echo   [FAILED] %%~nxF
        )
    )
)

echo.
if !count! == 0 (
    echo No audio files found in input\
    echo Supported formats: wav / mp3 / m4a / mp4 / flac / ogg
) else (
    echo ==================================================
    if !errcount! == 0 (
        echo   Done. !count! file^(s^) processed successfully.
    ) else (
        echo   !count! file^(s^) processed, !errcount! failed.
    )
    echo   Output: %~dp0output\
    echo ==================================================
)
pause
