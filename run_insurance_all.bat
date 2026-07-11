@echo off
chcp 65001 > nul
title Ruby PHR Link - Full Insurance Ingestion
echo ===================================================
echo   Ruby PHR Link - 실손보험 대량 문서 취합 (57개 파일)
echo ===================================================
echo.
echo D:\남기동\수원\실손보험 폴더 내의 모든 의무기록/영수증 PDF 분석을 시작합니다.
echo.

:: 1. API 키 환경변수 체크 및 입력 요청
if "%ANTHROPIC_API_KEY%"=="" (
    echo [정보] ANTHROPIC_API_KEY 환경변수가 정의되어 있지 않습니다.
    set /p API_KEY="Anthropic API Key를 입력해 주십시오 (sk-ant-...): "
) else (
    echo [정보] 기존 ANTHROPIC_API_KEY 환경변수를 사용합니다.
    set API_KEY=%ANTHROPIC_API_KEY%
)

if not "%API_KEY%"=="" (
    set ANTHROPIC_API_KEY=%API_KEY%
)

echo.
echo 🤖 Claude 3.5 Sonnet 기반 OCR 분석 및 DB 적재 진행 중...
python "%~dp0document_parser.py" --dir "D:\남기동\수원\실손보험"
echo.
echo 📊 통합 데이터베이스 적재 현황 조회...
python "%~dp0db_manager.py" status
echo.
pause
