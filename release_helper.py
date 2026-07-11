#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
Ruby PHR Link - Release Helper v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
역할: 버전 제어, CHANGELOG 관리, Git 커밋/푸시 자동화 배포 관리자
주요 기능:
  - version.py 버전 번호 자동 업데이트
  - CHANGELOG.md 최상단에 신규 릴리즈 블록 자동 생성
  - git add, git commit, git tag, git push 원클릭 자동 실행
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import logging
import traceback
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

# ─── 경로 및 설정 ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
VERSION_FILE = BASE_DIR / "version.py"
CHANGELOG_FILE = BASE_DIR / "CHANGELOG.md"

LOG_FILE = BASE_DIR / "logs" / "app.log"
logger = logging.getLogger("RubyPHRLink.ReleaseHelper")
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

def log_error(msg):
    print(f"❌ ERROR: {msg}", file=sys.stderr)
    logger.error(msg)

def infer_release_section(commit_msg):
    text = commit_msg.strip()
    lower = text.lower()
    prefix, _, body = text.partition(":")
    clean_body = body.strip() if body else text

    if lower.startswith(("feat:", "feature:", "add:", "added:")):
        return "Added", clean_body
    if lower.startswith(("fix:", "bugfix:", "hotfix:")):
        return "Fixed", clean_body
    if lower.startswith(("sec:", "security:")):
        return "Security", clean_body
    if lower.startswith(("docs:", "doc:", "refactor:", "chore:", "test:", "perf:", "style:")):
        return "Changed", clean_body
    return "Changed", text

def build_release_notes(new_version, commit_msg):
    today_str = datetime.today().strftime("%Y-%m-%d")
    section, bullet = infer_release_section(commit_msg)
    return f"## [{new_version}] - {today_str}\n### {section}\n- {bullet}\n"

# ─── Git 명령어 실행 헬퍼 ───────────────────────────────────────────────────
def run_git_cmd(args):
    try:
        res = subprocess.run(args, capture_output=True, text=True, check=True, encoding="utf-8")
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        log_error(f"Git 명령 실행 실패: {' '.join(args)}")
        log_error(f"Stderr: {e.stderr}")
        raise

# ─── 배포 관리 주 실행부 ───────────────────────────────────────────────────────
def run_release(new_version, commit_msg):
    log_info("🚀 Ruby PHR Link 자동 릴리즈 배포 가동...")
    
    if not VERSION_FILE.exists():
        log_error("version.py 파일이 존재하지 않습니다.")
        return

    if not CHANGELOG_FILE.exists():
        log_error("CHANGELOG.md 파일이 존재하지 않습니다.")
        return

    try:
        # 1. version.py 업데이트
        log_info(f"📝 version.py 버전을 {new_version}으로 업데이트 중...")
        VERSION_FILE.write_text(f'# -*- coding: utf-8 -*-\nVERSION = "{new_version}"\n', encoding="utf-8")

        # 2. CHANGELOG.md 자동 삽입
        log_info("📝 CHANGELOG.md에 신규 릴리즈 노트 삽입 중...")
        changelog_content = CHANGELOG_FILE.read_text(encoding="utf-8")

        new_entry = "\n" + build_release_notes(new_version, commit_msg) + "\n"

        # '모든 주요 릴리즈 및 기능 개선 사항 기록.' 텍스트 뒤에 신규 버전 블록을 밀어넣음
        target_marker = "모든 주요 릴리즈 및 기능 개선 사항 기록."
        if target_marker in changelog_content:
            parts = changelog_content.split(target_marker, 1)
            updated_changelog = parts[0] + target_marker + "\n" + new_entry + parts[1]
            CHANGELOG_FILE.write_text(updated_changelog, encoding="utf-8")
        else:
            # 마커가 없는 경우 맨 앞에 덧붙임
            CHANGELOG_FILE.write_text(new_entry + "\n" + changelog_content, encoding="utf-8")

        # 3. Git 자동화 커밋 및 푸시
        log_info("📦 Git 스테이징 및 커밋 준비 중...")
        run_git_cmd(["git", "add", "version.py", "CHANGELOG.md"])
        
        # 추가 변경 사항이 있는지 스테이징 검사
        status = run_git_cmd(["git", "status", "--porcelain"])
        if not status:
            log_info("ℹ 변경 사항이 없어 깃 커밋을 스킵합니다.")
            return

        commit_title = f"release: v{new_version} - {commit_msg}"
        log_info(f"💾 Git 커밋 생성 중: {commit_title}")
        run_git_cmd(["git", "commit", "-m", commit_title])

        # 원격 푸시
        log_info("🌐 GitHub 원격 저장소로 푸시 중...")
        run_git_cmd(["git", "push"])

        tag_name = f"v{new_version}"
        existing_tag = run_git_cmd(["git", "tag", "--list", tag_name])
        if not existing_tag:
            log_info(f"🏷️ Git 태그 생성 중: {tag_name}")
            run_git_cmd(["git", "tag", "-a", tag_name, "-m", tag_name])
            run_git_cmd(["git", "push", "origin", tag_name])
        else:
            log_info(f"ℹ️ Git 태그 {tag_name} 는 이미 존재합니다.")

        if shutil.which("gh"):
            release_notes = build_release_notes(new_version, commit_msg).strip() + "\n"
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".md") as tmp:
                tmp.write(release_notes)
                notes_path = tmp.name
            try:
                release_view = subprocess.run(
                    ["gh", "release", "view", tag_name],
                    capture_output=True,
                    text=True,
                    encoding="utf-8"
                )
                if release_view.returncode == 0:
                    log_info(f"📝 GitHub 릴리즈 {tag_name} 업데이트 중...")
                    run_git_cmd(["gh", "release", "edit", tag_name, "--notes-file", notes_path])
                else:
                    log_info(f"📝 GitHub 릴리즈 {tag_name} 생성 중...")
                    run_git_cmd(["gh", "release", "create", tag_name, "--title", tag_name, "--notes-file", notes_path])
            finally:
                try:
                    os.unlink(notes_path)
                except OSError:
                    pass
        else:
            log_info("ℹ gh CLI가 없어 GitHub 릴리즈 생성은 건너뜁니다.")

        log_info(f"🎉 릴리즈 v{new_version} 배포가 성공적으로 완료되었습니다!")

    except Exception as e:
        log_error(f"릴리즈 배포 중 치명적인 실패 발생: {e}")
        log_error(traceback.format_exc())

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python release_helper.py [신규버전] \"[릴리즈 메시지]\"")
        print("예시: python release_helper.py 1.4.0 \"자연어 Q&A 릴리즈 기능 및 엑셀 대량 마이그레이션 모듈 구현 완료\"")
        sys.exit(1)
        
    version_input = sys.argv[1].strip()
    msg_input = sys.argv[2].strip()
    
    run_release(version_input, msg_input)
