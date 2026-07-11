# 📋 CHANGELOG - Ruby PHR Link
모든 주요 릴리즈 및 기능 개선 사항 기록.

## [1.5.1] - 2026-07-11
### Added
- `claim_helper.py` 추가: 미청구(UNCLAIMED) 실손보험 내역 조회 및 복사용 명세 출력
- `--claim-all` 옵션 추가: 조회된 미청구 항목을 `CLAIMED` 상태로 일괄 전환

### Changed
- 실손보험 청구 흐름을 “조회 → 출력 → 일괄 전환” 중심으로 정리


## [1.5.0] - 2026-07-11
### Changed
- feat: Add app_server.py API server and pre-aggregated database stats to NL agent


## [1.4.0] - 2026-07-11
### Changed
- feat: Add release.bat and apply RotatingFileHandler for log rotation


## [1.3.1] - 2026-07-11
### Changed
- CHANGELOG 및 자동 릴리즈 헬퍼 탑재


## [1.3.0] - 2026-07-11
### Added
- 대용량 파일 취합용 진행률(%) 및 예상 완료시간(ETA) 출력 로직 탑재 (`document_parser.py`).
- 엑셀 수동 마이그레이션 도구 (`excel_importer.py`) 작성 및 실행 성공 (과거 27건 진료기록 이관 완료).
- 원클릭 로컬 테스트 및 자연어 Q&A 세션을 위한 배치 파일 2종 (`run_insurance_test.bat`, `run_agent_query.bat`) 추가.

### Security
- 개인정보 보호를 위해 `.gitignore` 파일 개조 (SQLite `.db`, `logs/`, 한글 병원 진료 디렉토리 전체 배제).

## [1.2.0] - 2026-07-11
### Added
- 실손보험 청구 내역용 비용 정보 파싱 및 DB 연동 (`insurance_claims` 테이블 및 맵핑 기능).
- PDF 파싱 에러 시 프로세스가 멈추지 않는 '안전 루프 예외 처리 모드' 도입.

## [1.1.0] - 2026-07-11
### Changed
- Claude 모델을 유효하지 않은 `claude-fable-5`에서 현재 정상 서비스 중인 `claude-3-5-sonnet-20241022`로 마스터 변경.
- 외부 임의 디렉토리 스캔을 지원하기 위해 `--dir` 옵션 지원.

## [1.0.0] - 2026-07-11
### Added
- 개인 건강 기록(PHR) SQLite 스키마 설계 및 테이블 초기화기 (`db_manager.py`) 셋업.
- AI 영상 판독 결과의 로컬 데이터베이스 연동 파이프라인 탑재.
