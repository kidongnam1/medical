# Ruby PHR Link

개인 의료기록, 실손보험 청구, 건강검진 PDF/OCR, 엑셀 이관, 자연어 질의를 한 폴더에서 처리하는 로컬 PHR 도구입니다.

Latest release: `v1.5.1`

## 핵심 기능

- `document_parser.py`: 의무기록과 건강검진 PDF/이미지를 파싱해 SQLite DB에 적재
- `excel_importer.py`: 과거 수기 엑셀 데이터를 DB로 이관
- `claim_helper.py`: 미청구 실손보험 내역 조회 및 청구용 명세 출력
- `natural_language_agent.py` / `app_server.py`: DB 기반 자연어 건강 질의와 API 서버
- `annotate_report.py`: 의료 영상에 주석을 넣어 리포트 생성

## 실행 순서

1. DB 초기화 또는 상태 확인
   - `python db_manager.py`
2. 문서 대량 적재
   - `.\run_insurance_all.bat`
   - 또는 `python document_parser.py --dir "D:\남기동\수원\실손보험"`
3. 과거 엑셀 이관이 필요하면 실행
   - `python excel_importer.py`
4. 미청구 실손보험 내역을 확인
   - `python claim_helper.py`
5. 자연어 질의 또는 API 서버를 실행
   - `.\run_agent_query.bat`
   - 또는 `python app_server.py`
6. 릴리즈 전 점검
   - `python release_helper.py 1.5.2 "docs: update release notes" --dry-run`

## 스크린샷

- 대량 문서 취합 실행 화면
- 미청구 실손보험 조회 화면
- 자연어 질의 응답 화면
- API 서버 또는 대시보드 화면

## 저장소 구성

- `medical_history.db`: 로컬 의료 데이터베이스
- `logs/`: 실행 로그
- `import_documents/`: 입력 문서
- `raw_images/`, `annotated_images/`: 원본 및 주석 이미지
