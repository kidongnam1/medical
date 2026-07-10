#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
의료영상 AI 판독 보고서 생성기 v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
모델  : claude-fable-5
인증  : Claude.ai 구독 OAuth (PKCE, 브라우저 로그인)
입력  : 폴더 탐색기로 의료영상(JPG) 폴더 선택
출력  : 주석 이미지(.jpg) + HTML 판독 보고서 3종
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
필요 패키지: pip install anthropic pillow
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import os
import sys
import base64
import json
import math
import glob
import webbrowser
import urllib.parse
import urllib.request
import secrets
import hashlib
import time
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from io import BytesIO

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageDraw, ImageFont

try:
    import anthropic
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

# ─── 상수 ──────────────────────────────────────────────────────────────────
MODEL        = "claude-fable-5"
OAUTH_PORT   = 8765
REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/callback"
AUTH_URL     = "https://claude.ai/oauth/authorize"
TOKEN_URL    = "https://console.anthropic.com/v1/oauth/token"
API_KEY_URL  = "https://api.anthropic.com/v1/organizations/api_keys"
SCOPE        = "org:create_api_key"

CONFIG_DIR   = Path.home() / ".config" / "medical-ai-reporter"
CONFIG_FILE  = CONFIG_DIR / "config.json"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

RESAMPLE = Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.BICUBIC

# 색상 팔레트
C_RED    = (220,  40,  40)
C_ORANGE = (230, 130,  20)
C_YELLOW = (200, 175,   0)
C_GREEN  = ( 30, 170,  60)
C_CYAN   = ( 20, 200, 220)
C_WHITE  = (255, 255, 255)
C_DARK   = ( 12,  18,  28)
C_DGRAY  = ( 25,  32,  48)
C_MGRAY  = ( 45,  55,  75)
C_LGRAY  = (170, 180, 200)

SEV_COLOR = {"RED": C_RED, "ORANGE": C_ORANGE, "YELLOW": C_YELLOW, "GREEN": C_GREEN, "CYAN": C_CYAN}

# ─── 이미지 드로잉 유틸리티 ────────────────────────────────────────────────

def fnt(size, bold=False):
    for p in [
        r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def draw_badge(draw, cx, cy, text, color, r=30):
    draw.ellipse([cx-r+3, cy-r+3, cx+r+3, cy+r+3], fill=(0, 0, 0))
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color, outline=C_WHITE, width=4)
    f = fnt(max(r - 8, 12), bold=True)
    tb = draw.textbbox((0, 0), text, font=f)
    tw = tb[2] - tb[0]; th = tb[3] - tb[1]
    draw.text((cx - tw // 2, cy - th // 2 + 1), text, fill=C_WHITE, font=f)

def draw_arrow(draw, sx, sy, ex, ey, color, lw=10, hs=40):
    draw.line([(sx, sy), (ex, ey)], fill=color, width=lw)
    dx = ex - sx; dy = ey - sy
    d = math.hypot(dx, dy)
    if d == 0:
        return
    ux = dx / d; uy = dy / d
    a = math.pi / 7
    p1 = (ex - hs * (ux * math.cos(a) - uy * math.sin(a)),
          ey - hs * (uy * math.cos(a) + ux * math.sin(a)))
    p2 = (ex - hs * (ux * math.cos(a) + uy * math.sin(a)),
          ey - hs * (uy * math.cos(a) - ux * math.sin(a)))
    draw.polygon([(ex, ey), p1, p2], fill=color)

def draw_label(draw, x, y, title, lines, tc, iw=9999, ih=9999):
    tf = fnt(28, True); bf = fnt(22)
    pad = 12
    mw = 0
    for t in [title] + lines:
        b = draw.textbbox((0, 0), t, font=(tf if t == title else bf))
        mw = max(mw, b[2] - b[0])
    bw = mw + pad * 2
    ttb = draw.textbbox((0, 0), title, font=tf)
    th_title = ttb[3] - ttb[1]
    line_hs = [(draw.textbbox((0, 0), l, font=bf)[3] - draw.textbbox((0, 0), l, font=bf)[1]) for l in lines]
    total_h = th_title + sum(line_hs) + 5 * len(lines) + pad * 2 + 6
    x = max(4, min(x, iw - bw - 4))
    y = max(4, min(y, ih - total_h - 4))
    draw.rectangle([x - pad, y - pad, x + bw - pad, y + total_h - pad], fill=C_DGRAY, outline=tc, width=3)
    draw.rectangle([x - pad, y - pad, x + bw - pad, y - pad + th_title + 12], fill=tc)
    draw.text((x, y), title, fill=C_WHITE, font=tf)
    cy = y + th_title + 10
    for ln, lh in zip(lines, line_hs):
        draw.text((x, cy), ln, fill=C_LGRAY, font=bf)
        cy += lh + 5

def draw_oval(draw, box, color, w=8):
    for i in range(w):
        draw.ellipse([box[0] - i, box[1] - i, box[2] + i, box[3] + i], outline=color)

def draw_banner(img, text, sub="", color=C_RED):
    bh = 85 if sub else 62
    new = Image.new('RGB', (img.width, img.height + bh), C_DARK)
    d = ImageDraw.Draw(new)
    d.rectangle([0, 0, img.width, bh], fill=C_DGRAY)
    d.line([(0, bh - 2), (img.width, bh - 2)], fill=color, width=4)
    d.rectangle([0, 0, 7, bh], fill=color)
    d.text((18, 8), text, fill=color, font=fnt(32, True))
    if sub:
        d.text((20, 50), sub, fill=C_LGRAY, font=fnt(20))
    new.paste(img, (0, bh))
    return new

def draw_legend(img, items):
    d = ImageDraw.Draw(img)
    f = fnt(21); pad = 8; bs = 20; gap = 5
    mw = max((d.textbbox((0, 0), t, font=f)[2] - d.textbbox((0, 0), t, font=f)[0]) for _, t in items)
    lw = bs + gap + mw + pad * 2
    lh = len(items) * (bs + 5) + pad * 2
    iw, ih = img.size
    lx = iw - lw - 14; ly = ih - lh - 14
    d.rectangle([lx - pad, ly - pad, lx + lw - pad, ly + lh - pad], fill=C_DGRAY, outline=C_MGRAY, width=2)
    cy = ly
    for color, text in items:
        d.rectangle([lx, cy, lx + bs, cy + bs], fill=color, outline=C_WHITE, width=2)
        d.text((lx + bs + gap, cy + 2), text, fill=C_LGRAY, font=f)
        cy += bs + 5
    return img


# ─── OAuth 관리 ────────────────────────────────────────────────────────────

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """로컬 콜백 서버 — 인증 코드 수신"""
    auth_code  = None
    error_msg  = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            body = b"<html><body><h2>OK! \xec\xb0\xbd\xec\x9d\x84 \xeb\x8b\xab\xec\x95\x84\xec\xa3\xbc\xec\x84\xb8\xec\x9a\x94.</h2></body></html>"
        else:
            OAuthCallbackHandler.error_msg = params.get("error", ["unknown"])[0]
            body = b"<html><body><h2>Error</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class OAuthManager:
    """Claude.ai 구독 OAuth PKCE 플로우"""

    def __init__(self, client_id):
        self.client_id = client_id

    def _pkce_pair(self):
        verifier  = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return verifier, challenge

    def _exchange_code(self, code, verifier):
        data = urllib.parse.urlencode({
            "grant_type":    "authorization_code",
            "client_id":     self.client_id,
            "redirect_uri":  REDIRECT_URI,
            "code":          code,
            "code_verifier": verifier,
        }).encode()
        req = urllib.request.Request(
            TOKEN_URL, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())

    def run_flow(self, on_success, on_error):
        """백그라운드 스레드에서 OAuth 플로우 실행"""
        def _flow():
            verifier, challenge = self._pkce_pair()
            OAuthCallbackHandler.auth_code = None
            OAuthCallbackHandler.error_msg = None

            # 로컬 콜백 서버 시작
            try:
                server = HTTPServer(("localhost", OAUTH_PORT), OAuthCallbackHandler)
            except OSError:
                on_error("포트 8765가 이미 사용 중입니다.")
                return

            params = urllib.parse.urlencode({
                "response_type":         "code",
                "client_id":             self.client_id,
                "redirect_uri":          REDIRECT_URI,
                "scope":                 SCOPE,
                "code_challenge":        challenge,
                "code_challenge_method": "S256",
            })
            webbrowser.open(f"{AUTH_URL}?{params}")

            # 콜백 대기 (최대 120초)
            server.timeout = 120
            deadline = time.time() + 120
            while time.time() < deadline:
                server.handle_request()
                if OAuthCallbackHandler.auth_code or OAuthCallbackHandler.error_msg:
                    break
            server.server_close()

            if OAuthCallbackHandler.error_msg:
                on_error(f"인증 오류: {OAuthCallbackHandler.error_msg}")
                return
            if not OAuthCallbackHandler.auth_code:
                on_error("시간 초과: 120초 내 인증이 완료되지 않았습니다.")
                return

            try:
                token_data = self._exchange_code(OAuthCallbackHandler.auth_code, verifier)
            except Exception as e:
                on_error(f"토큰 교환 실패: {e}")
                return

            on_success(token_data)

        threading.Thread(target=_flow, daemon=True).start()


# ─── Claude 이미지 분석 ────────────────────────────────────────────────────

ANALYSIS_PROMPT = """당신은 의료영상 전문 판독 AI입니다. 아래 의료영상(X선/MRI/CT/BMD/RF)을 분석하고
반드시 아래 JSON 형식으로만 응답하십시오. JSON 외 다른 텍스트 없이 순수 JSON만 출력.

{
  "image_type": "CR|MR|CT|BMD|RF|DT|UNKNOWN",
  "body_part": "CERVICAL|THORACIC|LUMBAR|CHEST|KNEE|HIP|OTHER",
  "view": "LAT|AP|SAG|AX|COR|OTHER",
  "banner_title": "📸 사진 제목 (한국어, 30자 이내)",
  "banner_sub": "● 핵심 소견 요약 (한국어, 50자 이내)",
  "banner_color": "RED|ORANGE|YELLOW|GREEN|CYAN",
  "how_to_read": ["이 사진 보는 법 줄1", "줄2", "줄3"],
  "findings": [
    {
      "num": 1,
      "label": "① C5-C6 [중증] 🚨",
      "lines": ["소견 설명 줄1", "줄2"],
      "severity": "RED|ORANGE|YELLOW|GREEN",
      "x_pct": 0.7,
      "y_pct": 0.5,
      "arrow_from_x_pct": 0.3,
      "arrow_from_y_pct": 0.5
    }
  ],
  "normal_comparison": {
    "label": "▷ 정상 비교",
    "lines": ["정상 소견 설명"],
    "x_pct": 0.6,
    "y_pct": 0.3,
    "box": [0.3, 0.25, 0.65, 0.35]
  },
  "legend_items": [
    ["RED", "🚨 즉시병원: 설명"],
    ["GREEN", "✅ 정상 비교"]
  ],
  "korean_summary": "전체 소견 한국어 요약 (100자 이내)",
  "severity_overall": "RED|ORANGE|YELLOW|GREEN",
  "recommendation": "권고 내용 (50자 이내)"
}

x_pct, y_pct 는 이미지 너비/높이 대비 0.0~1.0 비율.
findings 가 없으면 [] 로 둠.
정상 소견이면 normal_comparison 만 채움."""


def analyze_image_with_claude(client, img_path, log_fn=None):
    """Claude Fable 5로 의료영상 분석 → JSON 반환"""
    if log_fn:
        log_fn(f"  🔍 분석 중: {os.path.basename(img_path)}")

    # 이미지 리사이즈 (API 한계: 5MB, 분석용 1024px 충분)
    img = Image.open(img_path).convert("RGB")
    max_dim = 1024
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), RESAMPLE)

    buf = BytesIO()
    img.save(buf, "JPEG", quality=90)
    b64_data = base64.b64encode(buf.getvalue()).decode()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ],
            }],
        )
        raw = response.content[0].text.strip()
        # JSON 블록 추출 (```json ... ``` 감싼 경우 대응)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        if log_fn:
            log_fn(f"  ⚠️ 분석 오류: {e}")
    return None


# ─── 이미지 주석 그리기 ───────────────────────────────────────────────────

def annotate_from_analysis(src_path, analysis, out_path):
    """Claude 분석 결과를 바탕으로 이미지에 주석 추가 → 저장"""
    img = Image.open(src_path).convert("RGB")
    iw, ih = img.size
    draw = ImageDraw.Draw(img)

    # "이 사진 보는 법" 박스
    how_lines = analysis.get("how_to_read", [])
    if how_lines:
        draw_label(draw, 20, 30, "📸 이 사진 보는 법", how_lines, C_CYAN, iw, ih)

    # 정상 비교 박스
    nc = analysis.get("normal_comparison")
    if nc:
        box = nc.get("box")
        if box and len(box) == 4:
            draw_oval(draw, [int(box[0]*iw), int(box[1]*ih), int(box[2]*iw), int(box[3]*ih)], C_GREEN, 6)
        draw_label(draw,
                   int(nc.get("x_pct", 0.6) * iw),
                   int(nc.get("y_pct", 0.3) * ih),
                   nc.get("label", "▷ 정상 비교"),
                   nc.get("lines", []),
                   C_GREEN, iw, ih)

    # 소견 주석
    badge_labels = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"]
    for idx, finding in enumerate(analysis.get("findings", [])):
        num_text = badge_labels[idx] if idx < len(badge_labels) else str(idx + 1)
        color = SEV_COLOR.get(finding.get("severity", "ORANGE"), C_ORANGE)
        fx = int(finding.get("x_pct", 0.5) * iw)
        fy = int(finding.get("y_pct", 0.5) * ih)
        ax = int(finding.get("arrow_from_x_pct", max(0, finding.get("x_pct", 0.5) - 0.2)) * iw)
        ay = int(finding.get("arrow_from_y_pct", finding.get("y_pct", 0.5)) * ih)

        draw_badge(draw, ax + 5, ay, num_text, color, r=32)
        draw_arrow(draw, ax + 40, ay, fx, fy, color, lw=10, hs=36)
        draw_label(draw, fx + 15, fy - 30,
                   finding.get("label", f"소견 {idx+1}"),
                   finding.get("lines", []),
                   color, iw, ih)

    # 배너 추가
    banner_color = SEV_COLOR.get(analysis.get("banner_color", "RED"), C_RED)
    img = draw_banner(img,
                      analysis.get("banner_title", "📸 의료영상"),
                      analysis.get("banner_sub", ""),
                      banner_color)

    # 범례
    legend_raw = analysis.get("legend_items", [])
    if legend_raw:
        legend = [(SEV_COLOR.get(c, C_LGRAY), t) for c, t in legend_raw]
        img = draw_legend(img, legend)

    img.save(out_path, "JPEG", quality=94)
    return os.path.getsize(out_path) // 1024


# ─── HTML 빌더 ────────────────────────────────────────────────────────────

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Malgun Gothic','맑은 고딕',sans-serif;background:#0d1117;color:#e6edf3;line-height:1.7}
.container{max-width:1100px;margin:0 auto;padding:24px 16px}
h1{font-size:2rem;color:#58a6ff;text-align:center;margin-bottom:8px}
h2{font-size:1.4rem;color:#79c0ff;border-left:4px solid #388bfd;padding-left:12px;margin:32px 0 16px}
h3{font-size:1.1rem;color:#a5d6ff;margin:18px 0 10px}
.subtitle{text-align:center;color:#8b949e;margin-bottom:24px;font-size:.95rem}
.warn{background:#3d1f1f;border:2px solid #f85149;border-radius:8px;padding:14px 18px;margin:16px 0;color:#ffa198}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}
.info-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.info-card .lbl{color:#8b949e;font-size:.85rem}
.info-card .val{color:#e6edf3;font-weight:600;margin-top:4px}
.sumbox{background:#0f1923;border:2px solid #388bfd;border-radius:10px;padding:18px;margin:20px 0}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:.93rem}
th{background:#1c2128;color:#79c0ff;padding:10px 12px;text-align:left;border-bottom:2px solid #388bfd}
td{padding:9px 12px;border-bottom:1px solid #21262d}
tr:hover td{background:#161b22}
.br{display:inline-block;border-radius:6px;padding:2px 10px;font-weight:700;font-size:.88rem}
.br-red{background:#da3633;color:#fff}
.br-org{background:#d4910a;color:#fff}
.br-yel{background:#b8860b;color:#fff}
.br-ok{background:#238636;color:#fff}
.secsum{background:#12201a;border:2px solid #2ea043;border-radius:8px;padding:14px 18px;margin:12px 0 18px}
.imgwrap{margin:18px 0;text-align:center}
.cap{color:#8b949e;font-size:.88rem;margin-top:8px;text-align:center}
.fc{background:#0f1923;border-radius:10px;border:1px solid #30363d;padding:16px 20px;margin:14px 0}
.fc.red{border-left:4px solid #f85149}.fc.org{border-left:4px solid #d29922}
.fc.yel{border-left:4px solid #e3b341}.fc.grn{border-left:4px solid #2ea043}
.ft{font-size:1.05rem;font-weight:700;margin-bottom:8px}
.ft.red{color:#ffa198}.ft.org{color:#f0c674}.ft.yel{color:#e3b341}.ft.grn{color:#7ee787}
footer{text-align:center;color:#484f58;font-size:.82rem;margin-top:40px;padding:20px 0;border-top:1px solid #21262d}
"""

SEV_CLS = {"RED": "red", "ORANGE": "org", "YELLOW": "yel", "GREEN": "grn"}
SEV_BR  = {"RED": "br-red", "ORANGE": "br-org", "YELLOW": "br-yel", "GREEN": "br-ok"}
SEV_EM  = {"RED": "🔴🔴", "ORANGE": "🟠", "YELLOW": "🟡", "GREEN": "✅"}


def b64img(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def build_html_report(folder_path, analyses, out_folder, hospital_name, exam_date):
    """분석 결과 + 주석 이미지로 HTML 3종 생성"""
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")
    annotated_dir = os.path.join(out_folder, "FINAL")

    def make_html(mode):
        include_cmp  = (mode in ["cmp", "full"])
        include_docs = (mode == "full")

        # 요약 테이블 행
        summary_rows = ""
        for fname, ana in analyses:
            if not ana:
                continue
            sev = ana.get("severity_overall", "YELLOW")
            br  = SEV_BR.get(sev, "br-yel")
            em  = SEV_EM.get(sev, "🟡")
            summary_rows += (
                f"<tr><td>{ana.get('banner_title','')}</td>"
                f"<td>{ana.get('korean_summary','')}</td>"
                f"<td><span class='br {br}'>{em}</span></td>"
                f"<td>{ana.get('recommendation','')}</td></tr>\n"
            )

        # 이미지 섹션
        img_sections = ""
        for fname, ana in analyses:
            if not ana:
                continue
            ann_name = os.path.splitext(os.path.basename(fname))[0] + f"_ann_{exam_date}.jpg"
            ann_path = os.path.join(annotated_dir, ann_name)
            if not os.path.exists(ann_path):
                continue
            sev = ana.get("severity_overall", "YELLOW")
            cls = SEV_CLS.get(sev, "yel")
            findings_html = "\n".join(
                f"<p>· {f.get('label','')} — {' | '.join(f.get('lines',[]))}</p>"
                for f in ana.get("findings", [])
            )
            img_sections += f"""
<div class="fc {cls}">
  <div class="ft {cls}">{ana.get('banner_title','')} {SEV_EM.get(sev,'')}</div>
  <div class="secsum"><h3>주요 소견</h3>{findings_html or '<p>· 특이 소견 없음</p>'}</div>
  <div class="imgwrap"><img src="{b64img(ann_path)}" style="max-width:100%;border-radius:8px;"></div>
  <p class="cap">{ana.get('korean_summary','')}</p>
</div>
"""

        # 명의 섹션 (full 모드)
        doctors_html = ""
        if include_docs:
            doctors_html = """
<h2>🏥 추천 전문의 (2025~2026 기준)</h2>
<p style="color:#8b949e;font-size:.9rem;margin-bottom:12px;">아래는 참고용입니다. 정확한 진료는 공식 병원을 통해 예약하십시오.</p>
<table>
<thead><tr><th>순위</th><th>이름</th><th>병원 / 과</th><th>전문</th><th>연락처</th></tr></thead>
<tbody>
<tr><td>🥇</td><td><b>이동호 교수</b></td><td>서울아산병원 정형외과</td><td>경추 척수증·요추디스크·최소침습수술</td><td>1688-7575</td></tr>
<tr><td>🥈</td><td><b>김근수 교수</b></td><td>강남세브란스 신경외과</td><td>경추 척수증·척추관협착증·EBS 명의</td><td>1599-6114</td></tr>
<tr><td>🥉</td><td><b>김승범 원장</b></td><td>강남나누리병원 척추센터</td><td>경추·요추 내시경수술·윌스학술상 2025</td><td>1688-9797</td></tr>
<tr><td>4</td><td><b>하윤 교수</b></td><td>세브란스병원 신경외과</td><td>경추연구회 회장 (2025~2026)</td><td>1599-1004</td></tr>
<tr><td>5</td><td><b>공두식 교수</b></td><td>삼성서울병원 신경외과</td><td>경추·요추 척추질환·헬스조선 명의</td><td>1599-3114</td></tr>
</tbody>
</table>
"""

        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>의료영상 판독 보고서 — {hospital_name} {exam_date}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<h1>🏥 의료영상 정밀 판독 보고서</h1>
<p class="subtitle">{hospital_name} · {exam_date} 촬영 · Claude Fable 5 AI 보조 분석</p>
<div class="warn">⚠️ <b>주의</b>: AI 보조 분석 참고용. 정확한 진단·치료는 전문의 공식 판독을 따르십시오.</div>

<h2>📋 검사 개요</h2>
<div class="info-grid">
  <div class="info-card"><div class="lbl">검사일</div><div class="val">{exam_date}</div></div>
  <div class="info-card"><div class="lbl">병원</div><div class="val">{hospital_name}</div></div>
  <div class="info-card"><div class="lbl">AI 모델</div><div class="val">claude-fable-5</div></div>
  <div class="info-card"><div class="lbl">분석 이미지</div><div class="val">{len(analyses)}장</div></div>
  <div class="info-card"><div class="lbl">분석일</div><div class="val">{today}</div></div>
</div>

<h2>📊 전체 요약표</h2>
<table>
<thead><tr><th>영상</th><th>소견</th><th>위험도</th><th>권고</th></tr></thead>
<tbody>{summary_rows}</tbody>
</table>

<h2>🖼 주석 이미지 상세</h2>
{img_sections}

{doctors_html}

<footer>
  ⚠️ Claude Fable 5 AI 보조 분석 보고서 · 정확한 진단은 전문의 판독을 따르십시오<br>
  촬영일: {exam_date} · 분석일: {today}
</footer>
</div></body></html>"""

    results = {}
    for mode, suffix in [
        ("ann",  f"판독보고서_{hospital_name}_{exam_date}_정밀_주석포함"),
        ("cmp",  f"판독보고서_{hospital_name}_{exam_date}_정상비교포함"),
        ("full", f"판독보고서_{hospital_name}_{exam_date}_최종완성"),
    ]:
        html = make_html(mode)
        out_path = os.path.join(out_folder, f"{suffix}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        results[suffix] = out_path
    return results


# ─── 설정 관리 ────────────────────────────────────────────────────────────

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


try:
    import customtkinter as ctk  # type: ignore[import]
    CTK = True
except ImportError:
    CTK = False

# ─── 디자인 토큰 ────────────────────────────────────────────────────────────
# (CustomTkinter 색상 시스템)
BG        = "#0D1117"
CARD      = "#161B22"
CARD2     = "#1C2128"
BORDER    = "#30363D"
BLUE      = "#388BFD"
BLUE_D    = "#1F6FEB"
GREEN     = "#3FB950"
GREEN_D   = "#238636"
ORANGE    = "#D29922"
RED_C     = "#F85149"
TEXT1     = "#E6EDF3"
TEXT2     = "#8B949E"
TEXT3     = "#484F58"

# ─── 메인 GUI ─────────────────────────────────────────────────────────────

_AppBase: type = ctk.CTk if CTK else tk.Tk  # type: ignore[union-attr]

class App(_AppBase):  # type: ignore[misc]
    def __init__(self):
        super().__init__()
        if CTK:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

        self.title("의료영상 AI 판독 보고서 생성기")
        self.geometry("1080x760")
        self.configure(fg_color=BG if CTK else BG, bg=BG)
        self.minsize(900, 640)
        self.resizable(True, True)

        self.cfg    = load_config()
        self.client = None
        self._build_ui()
        self._refresh_auth_status()
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    # ── UI 구성 ─────────────────────────────────────────────────────────

    def _build_ui(self):
        # 루트 그리드: 2열 (좌=컨트롤, 우=로그)
        self.grid_columnconfigure(0, weight=0, minsize=370)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 좌측 패널 ──────────────────────────────────────────────────
        left = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                            border_width=0) if CTK else tk.Frame(self, bg=CARD)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        # 브랜드 헤더
        hdr_frame = ctk.CTkFrame(left, fg_color=CARD2, corner_radius=0) if CTK else tk.Frame(left, bg=CARD2)
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 1))
        self._lbl(hdr_frame, "🏥  Medical AI Reporter", size=15, bold=True, color=BLUE, pad=(20,14)).pack(anchor="w")
        self._lbl(hdr_frame, "claude-fable-5  ·  구독 OAuth", size=10, color=TEXT2, pad=(21,0)).pack(anchor="w")
        self._lbl(hdr_frame, "", size=6, pad=(0,6)).pack()

        scroll_area = ctk.CTkScrollableFrame(left, fg_color=CARD, corner_radius=0) if CTK \
                      else tk.Frame(left, bg=CARD)
        scroll_area.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        left.grid_rowconfigure(1, weight=1)
        scroll_area.grid_columnconfigure(0, weight=1)

        # ── 인증 카드 ──────────────────────────────────────────────────
        self._section_title(scroll_area, "🔐  인증").pack(fill="x", padx=20, pady=(20,6))
        auth_card = self._card(scroll_area)
        auth_card.pack(fill="x", padx=14, pady=(0, 4))

        self.auth_dot    = self._lbl(auth_card, "●", size=14, color=TEXT3)
        self.auth_dot.grid(row=0, column=0, padx=(14,6), pady=10)
        self.auth_lbl    = self._lbl(auth_card, "연결되지 않음", size=11, color=TEXT2)
        self.auth_lbl.grid(row=0, column=1, sticky="w")
        auth_card.grid_columnconfigure(1, weight=1)

        btn_row = ctk.CTkFrame(auth_card, fg_color="transparent") if CTK else tk.Frame(auth_card, bg=CARD2)
        btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,12))

        self.btn_oauth = self._btn(btn_row, "  로그인", cmd=self._start_oauth, color=BLUE, w=160)
        self.btn_oauth.pack(side="left", padx=(0,6))
        self._btn(btn_row, "API 키", cmd=self._enter_api_key, color=CARD, w=80).pack(side="left", padx=(0,6))
        self._btn(btn_row, "⚙", cmd=self._show_settings, color=CARD, w=40).pack(side="left")

        # ── 폴더 카드 ──────────────────────────────────────────────────
        self._section_title(scroll_area, "📁  영상 폴더").pack(fill="x", padx=20, pady=(16,6))
        fc = self._card(scroll_area)
        fc.pack(fill="x", padx=14, pady=(0, 4))
        fc.grid_columnconfigure(0, weight=1)

        self.folder_var = tk.StringVar(value=self.cfg.get("last_folder", ""))
        fe = ctk.CTkEntry(fc, textvariable=self.folder_var, height=36,
                          fg_color=BG, border_color=BORDER,
                          text_color=TEXT1, font=("맑은 고딕", 10)) if CTK \
             else tk.Entry(fc, textvariable=self.folder_var, bg=BG, fg=TEXT1, font=("맑은 고딕",10))
        fe.grid(row=0, column=0, sticky="ew", padx=(12,6), pady=10)
        self._btn(fc, "📂", cmd=self._browse_folder, color=BLUE, w=44).grid(row=0, column=1, padx=(0,10))
        self._lbl(fc, "IHE_PDI/JPG 또는 일반 JPG 폴더", size=9, color=TEXT3, pad=(14,0)
                  ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0,10))

        # ── 옵션 카드 ──────────────────────────────────────────────────
        self._section_title(scroll_area, "⚙  검사 정보").pack(fill="x", padx=20, pady=(16,6))
        oc = self._card(scroll_area)
        oc.pack(fill="x", padx=14, pady=(0, 4))
        oc.grid_columnconfigure(1, weight=1)

        self.hospital_var = tk.StringVar(value=self.cfg.get("hospital", "병원"))
        self.date_var     = tk.StringVar(value=self.cfg.get("exam_date", "20240715"))
        self.max_img_var  = tk.IntVar(value=int(self.cfg.get("max_images", 15)))
        self.open_html_var= tk.BooleanVar(value=True)

        for r, (lbl_txt, var, w) in enumerate([
            ("병원명", self.hospital_var, 160),
            ("검사일 (YYYYMMDD)", self.date_var, 120),
        ]):
            self._lbl(oc, lbl_txt, size=10, color=TEXT2, pad=(14,0)).grid(
                row=r, column=0, sticky="w", padx=(14,8), pady=6)
            e = ctk.CTkEntry(oc, textvariable=var, height=32, width=w,
                              fg_color=BG, border_color=BORDER, text_color=TEXT1,
                              font=("맑은 고딕",10)) if CTK \
                else tk.Entry(oc, textvariable=var, bg=BG, fg=TEXT1, width=18)
            e.grid(row=r, column=1, sticky="w", padx=(0,14), pady=6)

        self._lbl(oc, "최대 이미지 수", size=10, color=TEXT2, pad=(14,0)).grid(
            row=2, column=0, sticky="w", padx=(14,8), pady=6)
        sp = ctk.CTkEntry(oc, textvariable=self.max_img_var, height=32, width=60,
                           fg_color=BG, border_color=BORDER, text_color=TEXT1,
                           font=("맑은 고딕",10)) if CTK \
             else tk.Spinbox(oc, from_=1, to=50, textvariable=self.max_img_var, width=5)
        sp.grid(row=2, column=1, sticky="w", padx=(0,14), pady=6)

        chk = ctk.CTkCheckBox(oc, text="완료 후 HTML 자동 열기",
                               variable=self.open_html_var,
                               text_color=TEXT2, font=("맑은 고딕",10),
                               fg_color=BLUE, hover_color=BLUE_D) if CTK \
              else tk.Checkbutton(oc, text="완료 후 HTML 자동 열기",
                                  variable=self.open_html_var, bg=CARD2, fg=TEXT2)
        chk.grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0,12))

        # ── 실행 버튼 ──────────────────────────────────────────────────
        run_frame = ctk.CTkFrame(scroll_area, fg_color="transparent") if CTK \
                    else tk.Frame(scroll_area, bg=CARD)
        run_frame.pack(fill="x", padx=14, pady=(12, 20))
        self.btn_run = ctk.CTkButton(
            run_frame, text="▶   보고서 생성 시작",
            command=self._run, height=50,
            fg_color=GREEN_D, hover_color=GREEN,
            font=("맑은 고딕", 13, "bold"),
            corner_radius=10
        ) if CTK else tk.Button(run_frame, text="▶ 보고서 생성 시작",
                                 command=self._run, bg=GREEN_D, fg="white",
                                 font=("맑은 고딕",12,"bold"), pady=12)
        self.btn_run.pack(fill="x")

        # ── 우측 패널 ──────────────────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0) if CTK \
                else tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # 진행 상태 바
        prog_card = self._card(right, color=CARD)
        prog_card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        prog_card.grid_columnconfigure(0, weight=1)

        self.progress_lbl = self._lbl(prog_card, "대기 중...", size=10, color=TEXT2, pad=(14,10))
        self.progress_lbl.grid(row=0, column=0, sticky="w")
        self.progress_pct = self._lbl(prog_card, "0%", size=10, color=BLUE, pad=(0,10))
        self.progress_pct.grid(row=0, column=1, padx=(0,14))

        self.progress = ctk.CTkProgressBar(prog_card, height=6,
                                            fg_color=BORDER, progress_color=BLUE,
                                            corner_radius=3) if CTK \
                        else ttk.Progressbar(prog_card, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0,14))
        if CTK:
            self.progress.set(0)

        # 로그 영역
        log_hdr = ctk.CTkFrame(right, fg_color="transparent") if CTK else tk.Frame(right, bg=BG)
        log_hdr.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        log_hdr.grid_columnconfigure(0, weight=1)
        log_hdr.grid_rowconfigure(1, weight=1)

        self._section_title(log_hdr, "📋  처리 로그").grid(row=0, column=0, sticky="w", pady=(0,6))

        log_wrap = ctk.CTkFrame(log_hdr, fg_color=CARD, corner_radius=10,
                                 border_width=1, border_color=BORDER) if CTK \
                   else tk.Frame(log_hdr, bg=CARD)
        log_wrap.grid(row=1, column=0, sticky="nsew")
        log_wrap.grid_columnconfigure(0, weight=1)
        log_wrap.grid_rowconfigure(0, weight=1)

        self.log_box = tk.Text(
            log_wrap, bg=CARD, fg=TEXT1,
            font=("Consolas", 9), state=tk.DISABLED,
            insertbackground=TEXT1, relief="flat",
            padx=14, pady=12, wrap="word",
            selectbackground=BLUE_D
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(log_wrap, command=self.log_box.yview, bg=CARD, troughcolor=CARD)
        sb.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=sb.set)

        # 로그 태그 (컬러 라인)
        self.log_box.tag_configure("ok",   foreground=GREEN)
        self.log_box.tag_configure("warn", foreground=ORANGE)
        self.log_box.tag_configure("err",  foreground=RED_C)
        self.log_box.tag_configure("info", foreground=BLUE)
        self.log_box.tag_configure("dim",  foreground=TEXT3)

    # ── 위젯 헬퍼 ───────────────────────────────────────────────────────

    def _lbl(self, parent, text, size=10, bold=False, color=TEXT1, pad=(0,0)):
        weight = "bold" if bold else "normal"
        if CTK:
            return ctk.CTkLabel(parent, text=text, font=("맑은 고딕", size, weight),
                                 text_color=color, padx=pad[0], pady=pad[1])
        return tk.Label(parent, text=text, bg=parent.cget("bg") if hasattr(parent,"cget") else CARD,
                        fg=color, font=("맑은 고딕", size, weight))

    def _card(self, parent, color=CARD2):
        if CTK:
            return ctk.CTkFrame(parent, fg_color=color, corner_radius=10,
                                 border_width=1, border_color=BORDER)
        return tk.Frame(parent, bg=color)

    def _btn(self, parent, text, cmd, color=BLUE, w=None):
        kw = dict(width=w) if w else {}
        if CTK:
            return ctk.CTkButton(parent, text=text, command=cmd,
                                  fg_color=color, hover_color=BLUE_D if color==BLUE else CARD,
                                  height=32, font=("맑은 고딕", 10), corner_radius=8, **kw)
        return tk.Button(parent, text=text, command=cmd, bg=color, fg="white",
                         font=("맑은 고딕",10), relief="flat")

    def _section_title(self, parent, text):
        if CTK:
            return ctk.CTkLabel(parent, text=text, font=("맑은 고딕", 11, "bold"),
                                 text_color=TEXT2)
        return tk.Label(parent, text=text, bg=CARD, fg=TEXT2, font=("맑은 고딕",11,"bold"))

    # ── 이벤트 ──────────────────────────────────────────────────────────

    def _browse_folder(self):
        initial = self.folder_var.get() or str(Path.home())
        folder = filedialog.askdirectory(title="영상 폴더 선택", initialdir=initial)
        if folder:
            self.folder_var.set(folder)
            self._auto_detect_info(folder)

    def _auto_detect_info(self, folder):
        name = os.path.basename(folder)
        m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{8})", name)
        if m:
            self.date_var.set(m.group().replace("-", ""))
        for kw, hn in [("강남베드로","강남베드로병원"),("안강","안강병원"),
                        ("필메디스","필메디스의원"),("아산","서울아산병원")]:
            if kw in name:
                self.hospital_var.set(hn); break

    def _show_settings(self):
        win = ctk.CTkToplevel(self) if CTK else tk.Toplevel(self)
        win.title("설정 — OAuth Client ID")
        win.geometry("520x210")
        if CTK: win.configure(fg_color=CARD)
        else:   win.configure(bg=CARD)
        self._lbl(win, "Anthropic OAuth Client ID", size=12, bold=True, color=BLUE, pad=(20,16)).pack(anchor="w", padx=20, pady=(20,4))
        self._lbl(win, "console.anthropic.com → OAuth Apps → 앱 등록 후 발급", size=9, color=TEXT3).pack(anchor="w", padx=20)
        var = tk.StringVar(value=self.cfg.get("client_id", ""))
        e = ctk.CTkEntry(win, textvariable=var, height=36, width=460,
                          fg_color=BG, border_color=BORDER, text_color=TEXT1) if CTK \
            else tk.Entry(win, textvariable=var, width=52, bg=BG, fg=TEXT1)
        e.pack(pady=12, padx=20)
        def save():
            cid = var.get().strip()
            if cid: self.cfg["client_id"] = cid; save_config(self.cfg)
            win.destroy()
        self._btn(win, "저장", save, color=GREEN_D, w=120).pack()

    def _enter_api_key(self):
        from tkinter import simpledialog
        key = simpledialog.askstring(
            "API 키 직접 입력",
            "Anthropic API 키 입력 (sk-ant-...)\nOAuth 없이 즉시 사용 가능",
            parent=self
        )
        if key and key.strip():
            self.cfg["api_key"] = key.strip()
            save_config(self.cfg)
            try:
                self.client = anthropic.Anthropic(api_key=key.strip())
                self._set_auth_status(True, "API 키")
                self._log("🔑 API 키 입력 완료", "ok")
            except Exception as e:
                messagebox.showerror("오류", str(e))

    def _start_oauth(self):
        cid = self.cfg.get("client_id", "").strip()
        if not cid:
            messagebox.showinfo("Client ID 필요",
                "⚙ 설정 → Client ID를 먼저 입력하세요.\n"
                "또는 'API 키' 버튼으로 직접 입력 가능.")
            self._show_settings(); return

        self._log("🌐 Claude.ai 로그인 창 열는 중...", "info")
        if CTK: self.btn_oauth.configure(state="disabled")
        else:   self.btn_oauth.config(state="disabled")

        OAuthManager(cid).run_flow(
            on_success=lambda td: self.after(0, lambda: self._handle_token(td)),
            on_error  =lambda msg: self.after(0, lambda: (
                self._log(f"❌ OAuth 오류: {msg}", "err"),
                (self.btn_oauth.configure(state="normal") if CTK
                 else self.btn_oauth.config(state="normal"))
            ))
        )

    def _handle_token(self, td):
        token = td.get("access_token") or td.get("api_key") or td.get("token","")
        if not token:
            self._log(f"❌ 토큰 파싱 실패: {list(td.keys())}", "err"); return
        self.cfg["api_key"] = token; save_config(self.cfg)
        try:
            self.client = anthropic.Anthropic(api_key=token)
            self._set_auth_status(True, "Claude.ai OAuth")
            self._log("✅ OAuth 인증 완료!", "ok")
        except Exception as e:
            self._log(f"❌ 초기화 실패: {e}", "err")
        if CTK: self.btn_oauth.configure(state="normal")
        else:   self.btn_oauth.config(state="normal")

    def _refresh_auth_status(self):
        key = self.cfg.get("api_key","")
        if key:
            try:
                self.client = anthropic.Anthropic(api_key=key)
                self._set_auth_status(True, "저장된 인증")
            except Exception:
                self._set_auth_status(False)
        else:
            self._set_auth_status(False)

    def _set_auth_status(self, ok, method=""):
        if ok:
            dot_color = GREEN; status = f"연결됨  ({method})"
        else:
            dot_color = TEXT3; status = "연결되지 않음"
        if CTK:
            self.auth_dot.configure(text_color=dot_color)
            self.auth_lbl.configure(text=status, text_color=GREEN if ok else TEXT2)
        else:
            self.auth_dot.config(fg=dot_color)
            self.auth_lbl.config(text=status, fg=GREEN if ok else TEXT2)

    # ── 이미지 수집 ─────────────────────────────────────────────────────

    def _collect_images(self, folder):
        jpgs = []
        ihe_root = os.path.join(folder, "IHE_PDI", "JPG")
        if os.path.isdir(ihe_root):
            for series_dir in sorted(os.listdir(ihe_root)):
                sp = os.path.join(ihe_root, series_dir)
                if os.path.isdir(sp):
                    imgs = sorted(glob.glob(os.path.join(sp, "I*.jpg")))
                    if imgs:
                        jpgs.append(imgs[0])
                        if len(imgs) > 50:
                            jpgs.append(imgs[len(imgs)//2])
        else:
            for root, _, files in os.walk(folder):
                for f in sorted(files):
                    if f.lower().endswith((".jpg",".jpeg")):
                        jpgs.append(os.path.join(root, f))
        seen = set(); unique = []
        for p in jpgs:
            if p not in seen: seen.add(p); unique.append(p)
        return unique[:self.max_img_var.get()]

    # ── 실행 ────────────────────────────────────────────────────────────

    def _run(self):
        if not self.client:
            messagebox.showwarning("인증 필요", "먼저 로그인 또는 API 키를 입력하세요."); return
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("폴더 오류", "유효한 폴더를 선택하세요."); return

        self.cfg.update(last_folder=folder, hospital=self.hospital_var.get().strip() or "병원",
                        exam_date=self.date_var.get().strip() or "20240715")
        save_config(self.cfg)

        if CTK: self.btn_run.configure(state="disabled")
        else:   self.btn_run.config(state="disabled")
        self._clear_log()
        self._set_progress(0, "준비 중...")
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        folder    = self.folder_var.get().strip()
        hospital  = self.hospital_var.get().strip() or "병원"
        exam_date = self.date_var.get().strip() or "20240715"

        self._log(f"📁  {folder}", "dim")
        self._log(f"🏥  {hospital}  ·  {exam_date}", "info")

        images = self._collect_images(folder)
        if not images:
            self._log("❌  JPG 이미지를 찾을 수 없습니다.", "err")
            self.after(0, self._re_enable_run); return
        self._log(f"📸  {len(images)}장 발견", "info")

        out_folder = folder
        ann_dir    = os.path.join(out_folder, "FINAL")
        os.makedirs(ann_dir, exist_ok=True)
        analyses   = []
        total      = len(images)

        for i, img_path in enumerate(images):
            self._set_progress(int(i/total*80), f"분석 중 ({i+1}/{total})  {os.path.basename(img_path)}")
            ana = analyze_image_with_claude(self.client, img_path, self._log)
            analyses.append((img_path, ana))
            if ana:
                bname    = os.path.splitext(os.path.basename(img_path))[0]
                out_path = os.path.join(ann_dir, f"{bname}_ann_{exam_date}.jpg")
                try:
                    kb = annotate_from_analysis(img_path, ana, out_path)
                    self._log(f"  ✅  {os.path.basename(out_path)}  ({kb} KB)", "ok")
                except Exception as e:
                    self._log(f"  ⚠️  주석 오류: {e}", "warn")
            else:
                self._log(f"  ⚠️  분석 실패: {os.path.basename(img_path)}", "warn")

        self._set_progress(88, "HTML 보고서 생성 중...")
        self._log("\n📄  HTML 보고서 생성 중...", "info")
        try:
            html_files = build_html_report(folder, analyses, out_folder, hospital, exam_date)
            for path in html_files.values():
                sz = os.path.getsize(path)/1024/1024
                self._log(f"  ✅  {os.path.basename(path)}  ({sz:.1f} MB)", "ok")
        except Exception as e:
            self._log(f"  ❌  HTML 오류: {e}", "err"); html_files = {}

        self._set_progress(100, "✅  완료!")
        self._log(f"\n🎉  완료!  →  {out_folder}", "ok")
        self._log(f"     주석 이미지 {len([a for _,a in analyses if a])}장  ·  HTML {len(html_files)}종", "dim")

        if self.open_html_var.get() and html_files:
            full = [p for k,p in html_files.items() if "최종완성" in k]
            target = full[0] if full else list(html_files.values())[-1]
            self.after(600, lambda: webbrowser.open(f"file:///{target.replace(os.sep,'/')}"))

        self.after(0, self._re_enable_run)

    def _re_enable_run(self):
        if CTK: self.btn_run.configure(state="normal")
        else:   self.btn_run.config(state="normal")

    # ── 헬퍼 ────────────────────────────────────────────────────────────

    def _log(self, msg, tag=""):
        def _append():
            self.log_box.config(state=tk.NORMAL)
            start = self.log_box.index("end-1c")
            self.log_box.insert(tk.END, msg + "\n")
            if tag:
                end = self.log_box.index("end-1c")
                self.log_box.tag_add(tag, start, end)
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)
        self.after(0, _append)

    def _clear_log(self):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _set_progress(self, val, label=""):
        def _update():
            if CTK:
                self.progress.set(val / 100)
                self.progress_pct.configure(text=f"{val}%")
            else:
                self.progress["value"] = val
            if label:
                if CTK: self.progress_lbl.configure(text=label)
                else:   self.progress_lbl.config(text=label)
        self.after(0, _update)


# ─── 진입점 ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        # 창이 깜빡이고 닫힐 때 에러 확인용
        import tkinter as _tk
        _root = _tk.Tk()
        _root.withdraw()
        from tkinter import messagebox as _mb
        _mb.showerror("시작 오류", traceback.format_exc())
        _root.destroy()
