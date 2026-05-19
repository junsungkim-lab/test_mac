@echo off
chcp 65001 >nul
echo ==================================================
echo   메이플랜드 매크로 설치 (Windows)
echo ==================================================

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 없습니다.
    echo https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.
    echo 설치 시 "Add Python to PATH" 반드시 체크!
    pause
    exit /b 1
)

echo [OK] Python 확인됨
echo [설치중] pynput...
python -m pip install pynput --quiet

echo.
echo ==================================================
echo   설치 완료!
echo ==================================================
echo.
echo 실행 방법:
echo   python macro.py
echo.
echo 윈도우는 별도 권한 설정 없이 바로 실행됩니다.
echo.
pause
