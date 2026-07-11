#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Natural Language Medical Agent v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: 데이터베이스(SQLite) 기반 자연어 질의 및 답변 비서 (RAG)
주요 기능:
  - SQLite DB 정보를 요약/텍스트화하여 Claude Context로 주입
  - 수치형 데이터(혈압, 간수치 등)에 대한 연도별 통계 테이블 자동 시각화
  - 사용자의 임의 한글 자연어 질문에 대하여 최적의 건강 답변 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import sqlite3
import logging
import traceback
from pathlib import Path

# anthropic 임포트 시도
try:
    import anthropic
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

# ─── 경로 및 설정 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medical_history.db"
CONFIG_FILE = Path.home() / ".config" / "medical-ai-reporter" / "config.json"

LOG_FILE = BASE_DIR / "logs" / "app.log"
logger = logging.getLogger("RubyPHRLink.Agent")
logger.setLevel(logging.INFO)

# 파일 핸들러 (UTF-8 인코딩 명시)
if not (BASE_DIR / "logs").exists():
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

def log_info(msg):
    logger.info(msg)

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    logger.error(msg)

# ─── Anthropic 클라이언트 획득 ────────────────────────────────────────────────
def get_anthropic_client():
    # 1. 환경 변수 우선 확인
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        return anthropic.Anthropic(api_key=api_key)
        
    # 2. 설정 파일 확인 fallback
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            api_key = cfg.get("api_key", "").strip()
            if api_key:
                return anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            log_error(f"설정 파일 파싱 중 오류: {e}")
            
    raise FileNotFoundError("Anthropic API 키를 찾을 수 없습니다. 환경변수(ANTHROPIC_API_KEY) 또는 mar.py의 인증 정보를 세팅해 주십시오.")

# ─── DB 데이터를 텍스트 컨텍스트로 덤프 ───────────────────────────────────────────
def build_db_context():
    if not DB_PATH.exists():
        return "[오류: 데이터베이스 파일이 존재하지 않습니다. 먼저 db_manager.py를 실행하십시오.]"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    context_lines = []

    try:
        # 1. 진료 및 병원 방문 기록 요약
        cursor.execute("SELECT visit_id, visit_date, hospital_name, doctor_name, diagnosis, memo FROM hospital_visits ORDER BY visit_date DESC")
        visits = cursor.fetchall()
        context_lines.append("=== [진료 및 병원 방문 기록 (최근순)] ===")
        for v in visits:
            context_lines.append(f"- ID: {v[0]} | 날짜: {v[1]} | 병원: {v[2]} | 의사: {v[3] or '미상'} | 진단명: {v[4]} | 메모: {v[5] or ''}")
        context_lines.append("")

        # 2. 처방 약물 정보
        cursor.execute("""
            SELECT p.prescription_id, v.visit_date, v.hospital_name, p.medicine_name, p.dosage, p.duration_days, p.side_effects
            FROM prescriptions p
            LEFT JOIN hospital_visits v ON p.visit_id = v.visit_id
            ORDER BY v.visit_date DESC
        """)
        prescs = cursor.fetchall()
        context_lines.append("=== [처방받은 복용 약물 목록] ===")
        for p in prescs:
            context_lines.append(f"- 약물명: {p[3]} | 처방일: {p[1]} | 병원: {p[2]} | 복용법: {p[4]} | 복용기간: {p[5]}일 | 부작용: {p[6] or '없음'}")
        context_lines.append("")

        # 3. 의료 영상 AI 판독 이력
        cursor.execute("""
            SELECT m.image_id, v.visit_date, v.hospital_name, m.body_part, m.modality, m.ai_summary, m.raw_path, m.annotated_path
            FROM medical_images m
            LEFT JOIN hospital_visits v ON m.visit_id = v.visit_id
            ORDER BY v.visit_date DESC
        """)
        imgs = cursor.fetchall()
        context_lines.append("=== [의료 영상 AI 판독 이력] ===")
        for img in imgs:
            context_lines.append(f"- 영상ID: {img[0]} | 촬영일: {img[1]} | 병원: {img[2] or '로컬업로드'} | 부위: {img[3]} | 장비: {img[4]} | AI요약: {img[5]}")
            context_lines.append(f"  * 원본경로: {img[6]}")
            context_lines.append(f"  * 판독주석경로: {img[7] or '없음'}")
        context_lines.append("")

        # 4. 외부 서류 및 건강검진 텍스트 데이터 요약
        cursor.execute("SELECT doc_id, doc_date, doc_type, file_path, SUBSTR(full_text_content, 1, 800) FROM clinical_documents ORDER BY doc_date DESC")
        docs = cursor.fetchall()
        context_lines.append("=== [스캔 문서 및 건강검진 기록 요약] ===")
        for doc in docs:
            context_lines.append(f"- 문서ID: {doc[0]} | 일자: {doc[1]} | 종류: {doc[2]} | 파일경로: {doc[3]}")
            context_lines.append(f"  * 내용 초록: {doc[4]}...")
        context_lines.append("")

        # 5. 건강검진 수치형 지표 전체
        cursor.execute("""
            SELECT l.result_id, d.doc_date, l.test_name, l.test_value, l.reference_range, l.status
            FROM lab_results l
            JOIN clinical_documents d ON l.doc_id = d.doc_id
            ORDER BY l.test_name ASC, d.doc_date DESC
        """)
        labs = cursor.fetchall()
        context_lines.append("=== [종합 건강검진 수치 데이터] ===")
        for lab in labs:
            context_lines.append(f"- 검사항목: {lab[2]} | 검사일: {lab[1]} | 측정값: {lab[3]} | 기준치: {lab[4]} | 판정: {lab[5]}")
        context_lines.append("")

        # 6. 통증 및 컨디션 일지
        cursor.execute("SELECT log_date, body_part, pain_score, description FROM symptom_logs ORDER BY log_date DESC LIMIT 30")
        symptoms = cursor.fetchall()
        context_lines.append("=== [통증 및 증상 일일 로그 (최근 30건)] ===")
        for s in symptoms:
            context_lines.append(f"- 기록일: {s[0]} | 부위: {s[1]} | 통증점수(VAS): {s[2]}/10 | 특이사항: {s[3] or ''}")
        context_lines.append("")

    except sqlite3.Error as e:
        log_error(f"DB 데이터 수집 중 오류: {e}")
        log_error(traceback.format_exc())
    finally:
        conn.close()

    return "\n".join(context_lines)

# ─── 자연어 질의 수행 엔진 ──────────────────────────────────────────────────
def ask_agent(query_str):
    if not query_str.strip():
        print("질문 내용을 입력해 주십시오.")
        return

    # 1. DB 현황 데이터 수집
    db_context = build_db_context()

    # 2. AI 클라이언트 생성
    client = None
    try:
        client = get_anthropic_client()
    except Exception as e:
        log_error("API 인증 문제로 질의 처리를 중단합니다.")
        return

    # 3. 프롬프트 정의
    system_prompt = """당신은 사용자의 '개인 메디컬 데이터 웨어하우스'를 관리하는 수석 건강 비서입니다.
제시된 사용자의 실제 건강 데이터베이스 기록(진료 이력, 처방약, 통증 로그, 건강검진 수치, AI 영상 판독 결과)을 기반으로 질문에 답해 주십시오.

답변 규칙:
1. 오직 데이터베이스 내용에 기반해서 팩트만 대답하십시오. 없는 사실을 지어내지 마십시오.
2. 수치형 데이터(예: 혈압, 혈당, 간수치인 AST/ALT)의 변화 추이에 관한 질문을 받으면, 반드시 마크다운 표(Table) 형식으로 연도별/날짜별 비교 테이블을 예쁘게 구성하여 제공하십시오.
3. 통증 추이나 디스크 등의 병변 부위 질문이 오면, 연관된 AI 의료 영상 ID와 판독 주석 파일 경로를 함께 언급해 주어 사용자가 직접 찾아볼 수 있게 유도하십시오.
4. 전문의 진단이나 처방이 필요한 민감한 사안인 경우 공식 의료진 상담을 권고하는 멘트를 자연스럽게 하단에 덧붙여 주십시오.
"""

    print(f"🤔 질문: '{query_str}' 분석 및 DB 검색 중...")
    
    try:
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
        print("\n✨ [건강 비서 답변] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(answer)
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log_info(f"질문 성공 처리: {query_str}")
    except Exception as e:
        log_error(f"비서 응답 생성 실패: {e}")
        log_error(traceback.format_exc())

# ─── 메인 실행부 ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python natural_language_agent.py \"[질문할 내용]\"")
        print("예시: python natural_language_agent.py \"내 간 수치(ALT) 연도별 변화 추이 정리해줘\"")
        sys.exit(1)
        
    query = sys.argv[1]
    ask_agent(query)
