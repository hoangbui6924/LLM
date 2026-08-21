@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  ViMultiAgent — chay ca he thong bang MOT cu bam
REM
REM  Sau khi backend mount frontend/dist, ca giao dien lan API nam tren cung
REM  cong 8000. Script nay chi con phai lo ba viec: model o dau, Ollama da chay
REM  chua, va da build giao dien chua.
REM ===========================================================================

cd /d "%~dp0"
title ViMultiAgent

REM --- 1. Model nam o o E, khong phai thu muc mac dinh C:\Users\...\.ollama ---
REM Thieu bien nay thi Ollama bao khong co model va doi tai lai 2,5 GB.
if not defined OLLAMA_MODELS set "OLLAMA_MODELS=E:\DeepLearning\Ollama\models"
echo [1/4] OLLAMA_MODELS = %OLLAMA_MODELS%

REM --- 2. Ollama da chay chua ---
curl -s -o nul -m 3 http://localhost:11434/api/version
if errorlevel 1 (
    echo [2/4] Ollama chua chay — dang khoi dong...
    start "Ollama" /min cmd /c "set OLLAMA_MODELS=%OLLAMA_MODELS%&& ollama serve"

    set /a _doi=0
    :cho_ollama
    timeout /t 2 /nobreak >nul
    curl -s -o nul -m 3 http://localhost:11434/api/version
    if not errorlevel 1 goto ollama_ok
    set /a _doi+=1
    if %_doi% lss 15 goto cho_ollama

    echo.
    echo   LOI: Ollama khong khoi dong duoc sau 30 giay.
    echo   Thu mo Ollama bang tay roi chay lai file nay.
    pause
    exit /b 1
) else (
    echo [2/4] Ollama dang chay.
)
:ollama_ok

REM --- 3. Giao dien da build chua ---
if not exist "frontend\dist\index.html" (
    echo [3/5] Chua co frontend\dist — dang build...
    pushd frontend
    call npm run build
    popd
    if not exist "frontend\dist\index.html" (
        echo.
        echo   LOI: build giao dien that bai. Chay `npm install` trong thu muc frontend roi thu lai.
        pause
        exit /b 1
    )
) else (
    echo [3/5] Giao dien da build.
)

REM --- 4. Model PhoBERT ---
REM Du lieu (ml/data/*.csv) di kem du an, nhung model da train nang 518 MB nen
REM khong nam trong git. May moi copy ve se thieu no, va Router se lang le tut
REM ve luat tu khoa — tang hoc sau bien mat ma khong ai biet. Train luon o day.
if not exist "backend\ml\phobert_router\config.json" (
    echo [4/5] Chua co model PhoBERT.
    echo.
    echo   Du lieu da co san 1041 cau. Se huan luyen luon tu du lieu do.
    echo   Viec nay chay MOT LAN, mat khoang 50-55 phut tren CPU.
    echo   Bo qua thi chuong trinh van chay, nhung dinh tuyen kem chinh xac hon.
    echo.
    choice /c YN /n /m "  Huan luyen bay gio? [Y = co, N = bo qua] "
    if errorlevel 2 goto bo_qua_train

    pushd backend
    if not exist "ml\data\train.csv" python ml\build_dataset.py
    python ml\train_phobert.py
    popd
)
:bo_qua_train

REM --- 5. Backend, kiem luon giao dien ---
echo [5/5] Khoi dong backend tren http://localhost:8000 ...
echo.
echo   Trinh duyet se tu mo sau vai giay.
echo   Dong cua so nay de tat chuong trinh.
echo.

start "" /b cmd /c "timeout /t 6 /nobreak >nul && start http://localhost:8000"

cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000

endlocal
