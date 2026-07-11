# Ruby PHR Link

개인 의료기록, 실손보험 청구, 건강검진 PDF/OCR, 엑셀 이관, 자연어 질의를 한 폴더에서 처리하는 로컬 PHR 도구입니다.

Latest release: `v1.5.1`

## 핵심 기능

- `document_parser.py`: 의무기록과 건강검진 PDF/이미지를 파싱해 SQLite DB에 적재
- `excel_importer.py`: 과거 수기 엑셀 데이터를 DB로 이관
- `claim_helper.py`: 미청구 실손보험 내역 조회 및 청구용 명세 출력
- `natural_language_agent.py` / `app_server.py`: DB 기반 자연어 건강 질의와 API 서버
- `annotate_report.py`: 의료 영상에 주석을 넣어 리포트 생성

## 실행 예시

```powershell
.\run_insurance_test.bat
.\run_agent_query.bat
.\run_insurance_all.bat
```

## 저장소 구성

- `medical_history.db`: 로컬 의료 데이터베이스
- `logs/`: 실행 로그
- `import_documents/`: 입력 문서
- `raw_images/`, `annotated_images/`: 원본 및 주석 이미지
