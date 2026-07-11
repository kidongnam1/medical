#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Remote API Server v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: 광양 원격 연동 및 모바일 PWA 조회를 위한 경량 FastAPI 서버
포트: 8090
주요 라우트:
  - GET /api/dashboard : 통계 정보 (최다 방문 병원, 미청구금액 등)
  - GET /api/visits    : 진료 기록 리스트
  - GET /api/claims    : 실손보험 청구 내역 리스트
  - POST /api/ask      : AI 자연어 메디컬 질의 브릿지 API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import sqlite3
import logging
import traceback
from pathlib import Path
from datetime import datetime

# fastapi & uvicorn 임포트 시도
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"])
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn

# ─── 경로 및 설정 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medical_history.db"

LOG_FILE = BASE_DIR / "logs" / "app.log"
logger = logging.getLogger("RubyPHRLink.Server")
logger.setLevel(logging.INFO)

# 파일 핸들러 (5MB 회전 로거, UTF-8 인코딩)
from logging.handlers import RotatingFileHandler
if not (BASE_DIR / "logs").exists():
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# ─── FastAPI 인스턴스 ──────────────────────────────────────────────────────────
app = FastAPI(title="Ruby PHR Link Remote API", version="1.0.0")

# CORS 활성화 (광양 원격 런처 통신용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 요청 모델 ────────────────────────────────────────────────────────────────
class QueryModel(BaseModel):
    query: str

# ─── 데이터베이스 헬퍼 ─────────────────────────────────────────────────────────
def get_db_conn():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="데이터베이스 파일이 존재하지 않습니다.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── API 라우트 ────────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def get_dashboard_stats():
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # 최다 병원
        cursor.execute("SELECT hospital_name, COUNT(*) as cnt FROM hospital_visits GROUP BY hospital_name ORDER BY cnt DESC LIMIT 3")
        top_hospitals = [dict(r) for r in cursor.fetchall()]
        
        # 보험 청구 요약
        cursor.execute("""
            SELECT 
                COUNT(*) as total_claims,
                SUM(CASE WHEN claim_status = 'UNCLAIMED' THEN patient_share ELSE 0 END) as unclaimed_sum,
                SUM(CASE WHEN claim_status = 'CLAIMED' THEN patient_share ELSE 0 END) as claimed_sum,
                SUM(CASE WHEN claim_status = 'PAID' THEN paid_amount ELSE 0 END) as paid_sum
            FROM insurance_claims
        """)
        claim_row = cursor.fetchone()
        claim_summary = dict(claim_row) if claim_row else {}
        
        # 통증 평균
        cursor.execute("SELECT body_part, ROUND(AVG(pain_score), 1) as avg_p FROM symptom_logs GROUP BY body_part")
        pains = [dict(r) for r in cursor.fetchall()]
        
        return {
            "top_hospitals": top_hospitals,
            "insurance_summary": claim_summary,
            "pain_statistics": pains,
            "status": "success"
        }
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/visits")
def get_visits():
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM hospital_visits ORDER BY visit_date DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/claims")
def get_claims():
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT c.*, v.visit_date, v.hospital_name 
            FROM insurance_claims c
            LEFT JOIN hospital_visits v ON c.visit_id = v.visit_id
            ORDER BY v.visit_date DESC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/ask")
def ask_assistant(payload: QueryModel):
    query_str = payload.query.strip()
    if not query_str:
        raise HTTPException(status_code=400, detail="질문이 비어 있습니다.")
        
    try:
        # natural_language_agent의 ask_agent 함수를 빌려와 실행
        from natural_language_agent import build_db_context, get_anthropic_client
        db_context = build_db_context()
        client = get_anthropic_client()
        
        system_prompt = """당신은 사용자의 '개인 메디컬 데이터 웨어하우스'를 관리하는 수석 건강 비서입니다.
제시된 사용자의 실제 건강 데이터베이스 기록(진료 이력, 처방약, 통증 로그, 건강검진 수치, AI 영상 판독 결과)을 기반으로 질문에 답해 주십시오.
마크다운 포맷으로 대답하십시오.
"""
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": f"--- [사용자 건강 데이터베이스 정보] ---\n{db_context}\n\n--- [질문] ---\n{query_str}"
            }]
        )
        answer = response.content[0].text.strip()
        return {"answer": answer, "status": "success"}
    except Exception as e:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI 비서 응답 생성 오류: {e}")

# ─── 메인 실행 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("app_server:app", host="0.0.0.0", port=8090, reload=True)
