@echo off
chcp 65001 > nul
title Ruby PHR Link - AI Medical Agent Q&A
echo ===================================================
echo   Ruby PHR Link - 자연어 AI 메디컬 비서 (RAG)
echo ===================================================
echo.
echo 질문을 입력하시면 데이터베이스의 진료/복약/영상/검진 기록을 바탕으로
echo Claude 3.5 Sonnet 비서가 맞춤 분석을 수행하여 대답해 드립니다.
echo.
echo [추천 질문 예시]
echo  - "내가 2020년에 다녀온 병원 목록과 본인부담금 총액을 계산해줘"
echo  - "내 간 수치(ALT)와 혈압의 연도별 변화 추이를 표로 그려줘"
echo  - "목디스크(M502)로 치료받은 병원과 처방 내역 알려줘"
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

:loop
echo.
echo ---------------------------------------------------
set /p QUERY="질문 입력 (종료하려면 q 입력): "
if "%QUERY%"=="q" goto end
if "%QUERY%"=="" goto loop

python "%~dp0natural_language_agent.py" "%QUERY%"
goto loop

:end
echo.
echo 이용해 주셔서 감사합니다.
pause
