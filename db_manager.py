#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Database Manager v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: SQLite 데이터베이스 및 6대 테이블 설계 구축
주요 기능:
  - D:\남기동\수원\data\medical_history.db 파일 및 스키마 초기화
  - 필수 폴더 트리 자동 생성 (import_documents, raw_images, annotated_images)
  - logging 및 sys.stdout을 통한 정합성 검증 및 로그 관리
  - 검증용 드라이런 데이터(샘플 데이터) 탑재 기능
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import sqlite3
import logging
import traceback
from datetime import datetime
from pathlib import Path

# ─── 경로 설정 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medical_history.db"

# 데이터 저장을 위한 물리적 폴더들
REQUIRED_FOLDERS = [
    BASE_DIR / "import_documents",   # 외부 건강검진 PDF / 의무기록 파일용
    BASE_DIR / "raw_images",          # 원본 촬영 의료 영상용
    BASE_DIR / "annotated_images",    # AI 판독 주석이 가미된 의료 영상용
    BASE_DIR / "logs"                 # 시스템 로그용
]

# ─── 로깅 구성 ────────────────────────────────────────────────────────────
LOG_FILE = BASE_DIR / "logs" / "app.log"
BASE_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("RubyPHRLink")
logger.setLevel(logging.INFO)

# 파일 핸들러 (5MB 회전 로거, UTF-8 인코딩)
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 콘솔 출력을 화면과 로깅에 동시에 남기는 헬퍼 함수
def log_info(msg):
    print(msg)
    logger.info(msg)

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    logger.error(msg)

# ─── 스키마 생성 ──────────────────────────────────────────────────────────
SCHEMA = """
-- 1. 진료 이력 테이블 (병원 방문 기록)
CREATE TABLE IF NOT EXISTS hospital_visits (
    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_date TEXT NOT NULL,          -- YYYY-MM-DD
    hospital_name TEXT NOT NULL,
    doctor_name TEXT,
    diagnosis TEXT,
    memo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 처방 약물 테이블
CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER,
    medicine_name TEXT NOT NULL,
    dosage TEXT,                       -- 예: 1일 3회 식후 30분
    duration_days INTEGER,
    side_effects TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(visit_id) REFERENCES hospital_visits(visit_id) ON DELETE CASCADE
);

-- 3. 의료 영상 기록 테이블 (mar.py 연동)
CREATE TABLE IF NOT EXISTS medical_images (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER,
    body_part TEXT NOT NULL,           -- CERVICAL, LUMBAR, KNEE 등
    modality TEXT NOT NULL,            -- MR, CR, CT 등
    raw_path TEXT NOT NULL,            -- 원본 로컬 파일 경로
    annotated_path TEXT,               -- AI 주석 이미지 저장 경로
    ai_summary TEXT,                   -- AI 정밀 판독 한 줄 요약
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(visit_id) REFERENCES hospital_visits(visit_id) ON DELETE SET NULL
);

-- 4. 외부 임상 문서 테이블 (의무기록 사본 / 건강검진표 PDF)
CREATE TABLE IF NOT EXISTS clinical_documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER,
    doc_type TEXT NOT NULL,            -- HEALTH_CHECK, MEDICAL_RECORD_COPY 등
    doc_date TEXT NOT NULL,            -- YYYY-MM-DD
    file_path TEXT NOT NULL,           -- 로컬 파일 경로
    full_text_content TEXT,            -- 스캔 문서 전체 OCR 결과물
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(visit_id) REFERENCES hospital_visits(visit_id) ON DELETE SET NULL
);

-- 5. 임상 실험실 검사 결과 테이블 (건강검진 수치 기록)
CREATE TABLE IF NOT EXISTS lab_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER,
    test_name TEXT NOT NULL,           -- AST, ALT, LDL, BloodPressure 등
    test_value REAL,
    reference_range TEXT,              -- 정상 참고 범위 (예: 0-40)
    status TEXT,                       -- NORMAL, HIGH, LOW
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES clinical_documents(doc_id) ON DELETE CASCADE
);

-- 6. 통증 및 일일 증상 로그 테이블
CREATE TABLE IF NOT EXISTS symptom_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date TEXT NOT NULL,            -- YYYY-MM-DD
    body_part TEXT NOT NULL,           -- NECK, LOW_BACK, SHOULDER 등
    pain_score INTEGER NOT NULL,       -- 0 (무통) ~ 10 (극통)
    description TEXT,                  -- 특이사항 및 골프 활동 제약 여부 등
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 실손보험 청구 관리 테이블
CREATE TABLE IF NOT EXISTS insurance_claims (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id INTEGER,
    doc_id INTEGER,
    total_cost REAL,                   -- 진료비 총액
    patient_share REAL,                -- 급여 본인부담금
    non_covered_cost REAL,             -- 비급여 비용
    claim_status TEXT DEFAULT 'UNCLAIMED', -- UNCLAIMED, CLAIMED, PAID, REJECTED
    claimed_date TEXT,                 -- YYYY-MM-DD
    paid_amount REAL,                  -- 환급액
    memo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(visit_id) REFERENCES hospital_visits(visit_id) ON DELETE SET NULL,
    FOREIGN KEY(doc_id) REFERENCES clinical_documents(doc_id) ON DELETE SET NULL
);
"""

# ─── 데이터베이스 초기화 ────────────────────────────────────────────────────
def init_db(db_path=DB_PATH):
    log_info("🔄 Ruby PHR Link 데이터베이스 초기화 시작...")
    
    # 1. 필수 물리 폴더 생성
    for folder in REQUIRED_FOLDERS:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            log_info(f"📂 폴더 생성 완료: {folder.relative_to(BASE_DIR.parent)}")

    # 2. SQLite 스키마 생성
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Foreign Key 활성화
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 스키마 스크립트 실행
        cursor.executescript(SCHEMA)
        conn.commit()
        log_info(f"✅ DB 파일 생성 및 테이블 구조화 완료: {db_path}")
        
    except sqlite3.Error as e:
        log_error(f"데이터베이스 스키마 생성 중 실패: {e}")
        log_error(traceback.format_exc())
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# ─── 드라이런 테스트 데이터 주입 ──────────────────────────────────────────────
def insert_sample_data(db_path=DB_PATH):
    log_info("🧪 드라이런 테스트용 샘플 데이터 주입 중...")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 중복 방지를 위한 단순 조회 검사
        cursor.execute("SELECT COUNT(*) FROM hospital_visits")
        if cursor.fetchone()[0] > 0:
            log_info("ℹ 이미 기존 데이터가 존재하므로 샘플 데이터 주입을 생략합니다.")
            return

        # 1. 진료 이력 주입
        cursor.execute("""
            INSERT INTO hospital_visits (visit_date, hospital_name, doctor_name, diagnosis, memo)
            VALUES (?, ?, ?, ?, ?)
        """, ('2024-07-24', '강남베드로병원', '이동호 교수', '경추 척수증, 추간판 탈출증', '골프 및 과격한 스윙 주의 지시받음.'))
        visit_id = cursor.lastrowid

        # 2. 처방약 주입
        cursor.execute("""
            INSERT INTO prescriptions (visit_id, medicine_name, dosage, duration_days, side_effects)
            VALUES (?, ?, ?, ?, ?)
        """, (visit_id, '셀렉스정 (소염진통제)', '1일 2회 식후 30분', 14, '경미한 속쓰림'))

        # 3. 의료 영상 기록 주입 (가상 경로)
        cursor.execute("""
            INSERT INTO medical_images (visit_id, body_part, modality, raw_path, annotated_path, ai_summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            visit_id, 'CERVICAL', 'MR', 
            'D:/medical_records/raw_images/2024/07/PAT_0001/CR_20240724_01.jpg',
            'D:/medical_records/annotated_images/2024/07/PAT_0001/CR_20240724_01_ann.jpg',
            'C5-C6 디스크 중증 탈출 및 경미한 척수 압박 소견'
        ))

        # 4. 외부 임상 문서 주입 (건강검진표 가정)
        cursor.execute("""
            INSERT INTO clinical_documents (visit_id, doc_type, doc_date, file_path, full_text_content)
            VALUES (?, ?, ?, ?, ?)
        """, (
            None, 'HEALTH_CHECK', '2024-05-10', 
            'D:/medical_records/import_documents/health_check_2024.pdf',
            '2024년도 종합건강검진 결과 보고서... [혈액검사] ALT: 38 U/L (정상), AST: 32 U/L (정상)... [혈압] 128/82 mmHg...'
        ))
        doc_id = cursor.lastrowid

        # 5. 임상 실험실 검사 결과 주입
        cursor.executemany("""
            INSERT INTO lab_results (doc_id, test_name, test_value, reference_range, status)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (doc_id, 'ALT', 38.0, '0-40', 'NORMAL'),
            (doc_id, 'AST', 32.0, '0-40', 'NORMAL'),
            (doc_id, 'SystolicBP', 128.0, '90-120', 'HIGH') # 경계형 고혈압
        ])

        # 6. 통증 및 일일 증상 로그 주입
        cursor.executemany("""
            INSERT INTO symptom_logs (log_date, body_part, pain_score, description)
            VALUES (?, ?, ?, ?)
        """, [
            ('2026-07-10', 'NECK', 4, '어제 골프 라운딩 이후 목덜미 뻐근함 발생. 스윙 어드레스 자세 시 가벼운 통증.'),
            ('2026-07-11', 'NECK', 2, '소염진통제 복용 후 호전됨. 통증 거의 사라짐.')
        ])

        conn.commit()
        log_info("✅ 테스트 샘플 데이터 주입 완료!")
        
    except sqlite3.Error as e:
        log_error(f"샘플 데이터 주입 실패: {e}")
        log_error(traceback.format_exc())
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# ─── 상태 조회 ─────────────────────────────────────────────────────────────
def print_status(db_path=DB_PATH):
    if not db_path.exists():
        log_info(f"⚠️ 데이터베이스 파일이 존재하지 않습니다: {db_path}")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        log_info(f"📊 [데이터베이스 현황 보고] - {db_path.name}")
        tables = ['hospital_visits', 'prescriptions', 'medical_images', 'clinical_documents', 'lab_results', 'symptom_logs']
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            log_info(f"  - {t:<20} : {count} 건")
            
    except sqlite3.Error as e:
        log_error(f"상태 조회 중 오류 발생: {e}")
    finally:
        if conn:
            conn.close()

# ─── 메인 실행부 ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    action = "init"
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()

    if action == "init":
        init_db()
        print_status()
    elif action == "test":
        init_db()
        insert_sample_data()
        print_status()
    elif action == "status":
        print_status()
    else:
        print(f"사용법: python db_manager.py [init | test | status]")
