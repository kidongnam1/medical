@echo off
chcp 65001 > nul
title Ruby PHR Link - Insurance Document OCR Test
echo ===================================================
echo   Ruby PHR Link - 실손보험 영수증 OCR 테스트 (3개 파일)
echo ===================================================
echo.
echo D:\남기동\수원\data\insurance_test 폴더 내부의 3개 파일 분석을 시작합니다.
echo.

:: 1. API 키 환경변수 체크 및 입력 요청
if "%ANTHROPIC_API_KEY%"=="" (
    echo [정보] ANTHROPIC_API_KEY 환경변수가 정의되어 있지 않습니다.
    set /p API_KEY="Anthropic API Key를 입력해 주십시오 (sk-ant-...): "
) else (
    echo [정보] 기존 ANTHROPIC_API_KEY 환경변수를 사용합니다.
    set API_KEY=%ANTHROPIC_API_KEY%
)

if "%API_KEY%"=="" (
    echo [경고] API 키 없이 실행 시, config.json 인증파일 검색을 시도합니다.
) else (
    set ANTHROPIC_API_KEY=%API_KEY%
)

echo.
echo [1/2] 🤖 Claude 3.5 Sonnet 기반 OCR 분석 및 DB 적재 진행 중...
python "%~dp0document_parser.py" --dir "%~dp0insurance_test"
echo.

echo [2/2] 📊 현재 통합 데이터베이스 적재 현황 조회...
python "%~dp0db_manager.py" status
echo.
echo ===================================================
echo   테스트 처리가 완료되었습니다. (로그: logs/app.log)
echo ===================================================
pause
