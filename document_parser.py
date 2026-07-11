#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Medical Document Parser v1.3.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: 건강검진표 PDF 및 의무기록 사본 이미지 OCR 및 DB 적재 (외부 경로 스캔 지원)
개선 사항 (v1.3.0):
  1. 안전 루프 예외 처리 모드 보강 (하나의 불량 PDF가 에러를 내더라도 멈추지 않고 다음 파일로 진행)
  2. AI 추출 프롬프트 확장 (병원명, 진단명, 진료비 비용 정보 추가 검출)
  3. 실손보험 청구 관리 테이블(insurance_claims) 및 진료기록 연동 자동 맵핑 기능 구현
  4. 대용량 배치 처리 시 진행률(%) 및 예상 완료시간(ETA) 표시 기능 구현
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import sqlite3
import logging
import traceback
import base64
import argparse
import re
import time
from pathlib import Path
from datetime import datetime

# pypdf 임포트 시도
try:
    import pypdf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
    import pypdf

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
IMPORT_DIR = BASE_DIR / "import_documents"
CONFIG_FILE = Path.home() / ".config" / "medical-ai-reporter" / "config.json"

LOG_FILE = BASE_DIR / "logs" / "app.log"
logger = logging.getLogger("RubyPHRLink.Parser")
logger.setLevel(logging.INFO)

# 파일 핸들러 (5MB 회전 로거, UTF-8 인코딩)
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

def log_info(msg):
    print(msg)
    logger.info(msg)

def log_warn(msg):
    print(f"⚠️ WARN: {msg}")
    logger.warning(msg)

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

# ─── 텍스트 및 이미지 분석 프롬프트 (비용 및 병원명 파싱 확장) ─────────────────────
PARSING_PROMPT = """당신은 의료 기록 및 진료비 영수증 분석 전문 AI입니다. 
제시된 의료 기록 텍스트(또는 이미지)를 정밀 분석하여 임상 정보 및 실손보험 청구용 수치 데이터를 JSON으로 정규화해 주십시오.

반드시 아래 JSON 형식으로만 대답하십시오. JSON 외에 다른 설명 텍스트는 절대 출력하지 마십시오.

{
  "doc_type": "HEALTH_CHECK|CLINICAL_NOTE|LAB_REPORT",
  "doc_date": "YYYY-MM-DD",        -- 건강검진일, 진료일, 또는 영수증 수납일
  "hospital_name": "병원/약국 이름", -- 기록에 나타난 병원 또는 약국 이름
  "diagnosis": "진단명 또는 소견명", -- 진단서, 처방전 등에 나타난 병명. 없으면 "미지정"
  "full_summary": "이 문서의 전반적인 의학/비용 소견 요약 (한글, 100자 이내)",
  "lab_results": [
    {
      "test_name": "ALT",           -- 수치 검사가 있는 경우 (AST, ALT, LDL, BloodPressure 등)
      "test_value": 35.2,
      "reference_range": "0-40",
      "status": "NORMAL|HIGH|LOW"
    }
  ],
  "insurance_claim": {             -- 진료비 영수증, 영수증 납입 확인서, 세부내역서인 경우 필수 입력 (금액만 추출)
    "total_cost": 535539.0,        -- 진료비 총액 (급여+비급여 총합 수납금액)
    "patient_share": 85000.0,      -- 급여 본인부담금
    "non_covered_cost": 450539.0,  -- 비급여 비용 총합
    "memo": "진료비 항목 상세 메모 (예: 두경부 MRI 검사비)"
  }
}

주의:
- 문서 내용 중에 진료비 총액, 환자부담금, 비급여 금액 등 금액 정보가 나타나면 'insurance_claim' 오브젝트를 반드시 정확한 숫자형태로 채우십시오.
- 진료비 영수증이나 처방전이 아니어서 비용 정보가 전혀 없는 경우 'insurance_claim'은 null로 설정하십시오.
- doc_date는 반드시 'YYYY-MM-DD' 형식을 따르며, 문서 내 실제 진료일이나 수납일을 기초로 찾으십시오.
"""

# ─── PDF에서 텍스트 추출 ─────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path):
    text = []
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
    except Exception as e:
        log_error(f"PDF 텍스트 추출 중 오류 ({pdf_path.name}): {e}")
    return "\n".join(text)

# ─── 이미지 파일을 Base64로 인코딩 ───────────────────────────────────────────
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# ─── AI를 통한 문서 파싱 ─────────────────────────────────────────────────────
def parse_document_with_ai(client, file_path, extracted_text=None):
    ext = file_path.suffix.lower()
    
    # 1. 메시지 컨텐츠 구성
    message_content = []
    
    if ext in [".jpg", ".jpeg", ".png"]:
        # 이미지 파일: 비전 API 호출
        b64_image = encode_image(file_path)
        media_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
        message_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_image
            }
        })
        message_content.append({
            "type": "text",
            "text": PARSING_PROMPT + "\n\n위 이미지를 정밀 OCR 분석하고 정규화된 JSON을 출력하세요."
        })
    else:
        # PDF 및 일반 텍스트
        if not extracted_text:
            extracted_text = "[추출된 텍스트가 비어 있습니다]"
            
        message_content.append({
            "type": "text",
            "text": f"{PARSING_PROMPT}\n\n--- [분석할 의료기록 텍스트 시작] ---\n{extracted_text}\n--- [텍스트 끝] ---"
        })

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": message_content
            }]
        )
        raw_text = response.content[0].text.strip()
        
        # JSON 블록 추출
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            return json.loads(m.group()), raw_text
        else:
            raise ValueError(f"AI 응답에서 유효한 JSON을 파싱하지 못했습니다.\n원문: {raw_text}")
            
    except Exception as e:
        log_error(f"Claude API 호출 및 분석 오류 ({file_path.name}): {e}")
        log_error(traceback.format_exc())
        return None, None

# ─── DB 적재 처리 (진료 및 영수증 연동) ─────────────────────────────────────────
def save_to_database(file_path, analysis_data, raw_content):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        doc_type = analysis_data.get("doc_type", "CLINICAL_NOTE")
        doc_date = analysis_data.get("doc_date", datetime.today().strftime("%Y-%m-%d"))
        hospital_name = analysis_data.get("hospital_name", "미상 병원").strip()
        diagnosis = analysis_data.get("diagnosis", "미지정").strip()
        
        # 1. hospital_visits 매핑 (동일 일자, 동일 병원이 없으면 신규 추가)
        cursor.execute("""
            SELECT visit_id FROM hospital_visits 
            WHERE visit_date = ? AND hospital_name = ?
        """, (doc_date, hospital_name))
        visit_row = cursor.fetchone()
        
        if visit_row:
            visit_id = visit_row[0]
            # 진단명 정보 업데이트 보강
            if diagnosis and diagnosis != "미지정":
                cursor.execute("""
                    UPDATE hospital_visits SET diagnosis = ? WHERE visit_id = ? AND (diagnosis = '미지정' OR diagnosis IS NULL)
                """, (diagnosis, visit_id))
        else:
            cursor.execute("""
                INSERT INTO hospital_visits (visit_date, hospital_name, doctor_name, diagnosis, memo)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_date, hospital_name, "미상", diagnosis, "의료 서류 취합 연동 건"))
            visit_id = cursor.lastrowid
        
        # 경로 예외 처리
        try:
            file_rel_path = str(file_path.relative_to(BASE_DIR))
        except ValueError:
            file_rel_path = str(file_path.resolve())

        full_text = raw_content if raw_content else analysis_data.get("full_summary", "")

        # 2. clinical_documents 테이블 적재
        cursor.execute("""
            INSERT INTO clinical_documents (visit_id, doc_type, doc_date, file_path, full_text_content)
            VALUES (?, ?, ?, ?, ?)
        """, (visit_id, doc_type, doc_date, file_rel_path, full_text))
        doc_id = cursor.lastrowid
        
        # 3. lab_results 테이블 적재
        results = analysis_data.get("lab_results", [])
        if results:
            insert_data = []
            for r in results:
                insert_data.append((
                    doc_id,
                    r.get("test_name", "UNKNOWN"),
                    r.get("test_value"),
                    r.get("reference_range", ""),
                    r.get("status", "NORMAL")
                ))
            cursor.executemany("""
                INSERT INTO lab_results (doc_id, test_name, test_value, reference_range, status)
                VALUES (?, ?, ?, ?, ?)
            """, insert_data)
            
        # 4. insurance_claims (실손보험 청구 관리) 테이블 적재
        claim_data = analysis_data.get("insurance_claim")
        if claim_data and isinstance(claim_data, dict):
            total_cost = claim_data.get("total_cost")
            patient_share = claim_data.get("patient_share")
            non_covered_cost = claim_data.get("non_covered_cost")
            memo = claim_data.get("memo", "")
            
            # 비용 정보가 최소 하나라도 실재하는 경우에만 적재
            if total_cost is not None or patient_share is not None or non_covered_cost is not None:
                cursor.execute("""
                    INSERT INTO insurance_claims (visit_id, doc_id, total_cost, patient_share, non_covered_cost, claim_status, memo)
                    VALUES (?, ?, ?, ?, ?, 'UNCLAIMED', ?)
                """, (visit_id, doc_id, total_cost, patient_share, non_covered_cost, memo))
                log_info(f"  💵 실손보험 진료비 적재 완료 (총액: {total_cost}원, 본인부담: {patient_share}원, 비급여: {non_covered_cost}원)")

        conn.commit()
        log_info(f"💾 DB 저장 완료 (Doc ID: {doc_id}, Lab Results: {len(results)}건)")
        return True
    except sqlite3.Error as e:
        log_error(f"SQLite DB 적재 중 실패 ({file_path.name}): {e}")
        log_error(traceback.format_exc())
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# ─── 폴더 스캔 및 처리 ───────────────────────────────────────────────────────
def process_imports(target_dir=None):
    log_info("🔄 Ruby PHR Link 외부 문서 스캔 파이프라인 가동...")
    
    scan_dir = Path(target_dir) if target_dir else IMPORT_DIR
    if not scan_dir.exists():
        scan_dir.mkdir(parents=True, exist_ok=True)
        log_info(f"📂 수집용 폴더를 자동 생성했습니다: {scan_dir}")
        return

    # DB 존재 여부 확인
    if not DB_PATH.exists():
        log_warn("⚠️ DB 파일이 존재하지 않습니다. db_manager.py를 먼저 실행하여 초기화하십시오.")
        return

    # 스캔할 확장자 파일 리스트업
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    files_to_process = [p for p in scan_dir.iterdir() if p.suffix.lower() in allowed_extensions]

    if not files_to_process:
        log_info(f"ℹ 스캔 폴더({scan_dir.name})가 비어 있습니다. 새로 스캔할 문서가 없습니다.")
        return

    # 이미 DB에 처리된 파일 경로 리스트 조회
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM clinical_documents")
    processed_paths = {row[0] for row in cursor.fetchall()}
    conn.close()

    # 중복되지 않은 신규 작업 필터링
    to_process = []
    for file_path in files_to_process:
        try:
            file_rel_path = str(file_path.relative_to(BASE_DIR))
        except ValueError:
            file_rel_path = str(file_path.resolve())

        if file_rel_path in processed_paths or str(file_path.resolve()) in processed_paths:
            continue
        to_process.append(file_path)

    total_jobs = len(to_process)
    if not to_process:
        log_info("ℹ 신규로 파싱 및 취합할 문서가 없습니다. 모든 파일이 이미 적재 완료된 상태입니다.")
        return

    log_info(f"🚀 총 {total_jobs}개의 신규 파일 처리를 시작합니다.")

    # AI 클라이언트 초기화
    client = None
    try:
        client = get_anthropic_client()
    except Exception:
        log_error("API 인증 문제로 파싱 프로세스를 중단합니다.")
        return

    success_count = 0
    failure_count = 0
    start_time = time.time()
    
    for idx, file_path in enumerate(to_process):
        # ─── 실시간 진행률 및 ETA 예상 시간 연산 ───
        percent = int(((idx) / total_jobs) * 100)
        if idx > 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining_jobs = total_jobs - idx
            eta_seconds = int(avg_time * remaining_jobs)
            if eta_seconds >= 60:
                eta_str = f"{eta_seconds // 60}분 {eta_seconds % 60}초"
            else:
                eta_str = f"{eta_seconds}초"
            progress_msg = f"⏳ [진행률] {percent}% ({idx}/{total_jobs}) | 예상 남은 시간: {eta_str}"
        else:
            progress_msg = f"⏳ [진행률] {percent}% ({idx}/{total_jobs}) | 남은 예상 시간 계산 중..."

        log_info(f"\n{progress_msg}")
        
        # ─── 안전 루프 예외 처리 모드 ───
        try:
            log_info(f"🔍 새 문서 발견: {file_path.name}")
            
            extracted_text = None
            if file_path.suffix.lower() == ".pdf":
                log_info(f"  📄 PDF 텍스트 추출 중 ({file_path.name})...")
                extracted_text = extract_text_from_pdf(file_path)
                log_info(f"  📄 텍스트 추출 완료 (크기: {len(extracted_text or '')}자)")

            # AI 파싱 수행
            log_info(f"  🤖 Claude AI 데이터 구조화 분석 진행 중...")
            analysis, raw_resp = parse_document_with_ai(client, file_path, extracted_text)
            
            if analysis:
                # DB 적재
                raw_content = extracted_text if extracted_text else raw_resp
                if save_to_database(file_path, analysis, raw_content):
                    success_count += 1
                else:
                    failure_count += 1
            else:
                log_warn(f"  ⚠️ AI 분석 결과가 불완전하여 DB 적재를 스킵합니다: {file_path.name}")
                failure_count += 1
                
        except Exception as file_error:
            log_error(f"  ⚠️ 파일 처리 중 심각한 예외 발생 ({file_path.name}): {file_error}")
            logger.error(traceback.format_exc())
            failure_count += 1
            continue

    log_info(f"\n📊 [취합 결과 리포트]")
    log_info(f"  - 성공적으로 적재 완료 : {success_count} 건")
    log_info(f"  - 분석/처리 실패 건수   : {failure_count} 건")
    
    if success_count > 0:
        try:
            import db_manager
            db_manager.print_status()
        except ImportError:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ruby PHR Link - Document Parser")
    parser.add_argument("--dir", type=str, help="스캔할 의료기록 PDF/이미지 폴더 경로")
    args = parser.parse_args()

    try:
        process_imports(args.dir)
    except Exception as e:
        log_error(f"글로벌 예외 발생: {e}")
        log_error(traceback.format_exc())
