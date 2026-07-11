#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Insurance Claim Helper v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: 실손보험 미청구 내역 조회 및 청구 자동화 대리인
주요 기능:
  - SQLite DB에서 claim_status = 'UNCLAIMED' (미청구)인 항목들을 추출
  - 팩스 전송 및 보험사 청구서에 붙여넣을 수 있는 텍스트 명세 양식 자동 빌드
  - CLI 인자(--claim-all) 전달 시, 대상 항목들을 'CLAIMED' (청구 완료) 상태로 일괄 전환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import sqlite3
import logging
import traceback
import argparse
from pathlib import Path
from datetime import datetime

# ─── 경로 및 설정 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "medical_history.db"

LOG_FILE = BASE_DIR / "logs" / "app.log"
logger = logging.getLogger("RubyPHRLink.ClaimHelper")
logger.setLevel(logging.INFO)

# 파일 핸들러 (5MB 회전 로거, UTF-8 인코딩)
from logging.handlers import RotatingFileHandler
if not (BASE_DIR / "logs").exists():
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

def log_info(msg):
    print(msg)
    logger.info(msg)

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    logger.error(msg)

# ─── 미청구 내역 조회 및 명세 빌더 ──────────────────────────────────────────────
def run_claim_helper(claim_all=False):
    if not DB_PATH.exists():
        log_error(f"데이터베이스 파일이 존재하지 않습니다: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 1. 미청구 내역(UNCLAIMED) 조회
        cursor.execute("""
            SELECT c.claim_id, v.visit_date, v.hospital_name, v.diagnosis, 
                   c.total_cost, c.patient_share, c.non_covered_cost, c.memo, c.doc_id, d.file_path
            FROM insurance_claims c
            LEFT JOIN hospital_visits v ON c.visit_id = v.visit_id
            LEFT JOIN clinical_documents d ON c.doc_id = d.doc_id
            WHERE c.claim_status = 'UNCLAIMED'
            ORDER BY v.visit_date ASC
        """)
        rows = cursor.fetchall()
        
        if not rows:
            log_info("🎉 축하합니다! 현재 미청구(UNCLAIMED)된 실손보험 내역이 존재하지 않습니다.")
            log_info("   모든 의료 기록비가 청구 완료 상태입니다.")
            return

        total_unclaimed_cost = 0.0
        total_patient_share = 0.0
        total_non_covered = 0.0
        
        log_info("\n📢 [미청구 실손보험 대상 내역 명세서]")
        log_info("=" * 72)
        log_info(f"{'No':<3} | {'진료일':<10} | {'병원명':<16} | {'진료비총액':<9} | {'본인부담금':<9} | {'비급여액':<9}")
        log_info("-" * 72)
        
        claim_ids = []
        claim_texts = []
        
        for idx, r in enumerate(rows):
            cid, vdate, hname, diag, tcost, pshare, ncovered, memo, doc_id, fpath = r
            tcost = tcost or 0.0
            pshare = pshare or 0.0
            ncovered = ncovered or 0.0
            
            total_unclaimed_cost += tcost
            total_patient_share += pshare
            total_non_covered += ncovered
            claim_ids.append(cid)
            
            log_info(f"{idx+1:<3} | {vdate:<10} | {hname[:10]:<16} | {tcost:,.0f}원 | {pshare:,.0f}원 | {ncovered:,.0f}원")
            
            # 클립보드 복사용 개별 텍스트 빌드
            doc_str = f"  * 첨부 서류 경로: {fpath}" if fpath else "  * 첨부 서류: 없음 (영수증 실물 확인 필요)"
            claim_texts.append(
                f"[{idx+1}] 진료일: {vdate} | 병원명: {hname}\n"
                f"    - 진단명: {diag or '확인불가'}\n"
                f"    - 본인부담금: {pshare:,.0f}원 | 비급여 비용: {ncovered:,.0f}원 (총액: {tcost:,.0f}원)\n"
                f"    - 진료 메모: {memo or '없음'}\n"
                f"{doc_str}\n"
            )
            
        log_info("-" * 72)
        log_info(f"💰 합계 금액: 진료비 총액 {total_unclaimed_cost:,.0f}원 | 본인부담금 합계 {total_patient_share:,.0f}원 | 비급여 합계 {total_non_covered:,.0f}원")
        log_info("=" * 72)

        # 2. 복사용 청구서 명세서 출력
        log_info("\n📋 [보험사 제출용 텍스트 복사 양식]")
        log_info("───────────────────────────────────────────────────")
        today_str = datetime.today().strftime("%Y-%m-%d")
        log_info(f"실손의료비 보험금 청구 명세 (작성일: {today_str})")
        log_info(f"청구 대상 건수: 총 {len(rows)}건")
        log_info(f"청구 예정 총액: {total_patient_share:,.0f}원 (본인부담금 기준)")
        log_info("---------------------------------------------------")
        for txt in claim_texts:
            log_info(txt)
        log_info("───────────────────────────────────────────────────")

        # 3. 일괄 청구 상태 변경 (--claim-all)
        if claim_all:
            log_info(f"\n🔄 {len(claim_ids)}건의 미청구 항목을 'CLAIMED' (청구 완료) 상태로 전환 중...")
            placeholders = ",".join(["?"] * len(claim_ids))
            
            cursor.execute(f"""
                UPDATE insurance_claims 
                SET claim_status = 'CLAIMED', claimed_date = ? 
                WHERE claim_id IN ({placeholders})
            """, [today_str] + claim_ids)
            
            conn.commit()
            log_info("✅ 일괄 청구 전환 처리가 완료되었습니다! (상태: CLAIMED)")
        else:
            log_info("\n💡 꿀팁: 이 항목들을 청구 완료 상태로 바꾸시려면 아래 명령어를 실행하십시오.")
            log_info("   python claim_helper.py --claim-all")

    except sqlite3.Error as e:
        log_error(f"보험금 청구 도우미 구동 실패: {e}")
        log_error(traceback.format_exc())
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ruby PHR Link - Insurance Claim Helper")
    parser.add_argument("--claim-all", action="store_true", help="모든 미청구 대기 항목을 청구 완료(CLAIMED) 상태로 일괄 전환")
    args = parser.parse_args()

    run_claim_helper(args.claim_all)
