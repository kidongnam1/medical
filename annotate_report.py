"""
의료 영상 어노테이션 스크립트
이상 부위에 빨간색 표시 + 파란색 설명 추가
"""
import os
import base64
from PIL import Image, ImageDraw, ImageFont
import io

BASE_2026 = r"D:\남기동\수원\data\필메디스-2026-02-13\_report_필메디스\captures"
BASE_SPINE = r"D:\남기동\수원\data\필메디스-2026-07-06\_report_필메디스_0706\png"
OUT_DIR = r"D:\남기동\수원\data\필메디스_통합보고서\annotated"
os.makedirs(OUT_DIR, exist_ok=True)

def load_font(size=18):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", size)
    except:
        try:
            return ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", size)
        except:
            return ImageFont.load_default()

def img_to_b64(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def draw_annotation(img, shapes, labels):
    """
    shapes: list of ('rect'|'circle'|'arrow', coords, color)
    labels: list of (x, y, text, color, font_size)
    """
    draw = ImageDraw.Draw(img, 'RGBA')
    for shape_type, coords, color in shapes:
        if shape_type == 'rect':
            x0,y0,x1,y1 = coords
            # 테두리만 (채우기 없음)
            draw.rectangle([x0,y0,x1,y1], fill=None, outline=(*color, 240), width=5)
            # 모서리 강조
            cs = 10
            for cx,cy in [(x0,y0),(x1,y0),(x0,y1),(x1,y1)]:
                draw.rectangle([cx-cs,cy-cs,cx+cs,cy+cs], fill=(*color, 255), outline=None)
        elif shape_type == 'circle':
            x0,y0,x1,y1 = coords
            draw.ellipse([x0,y0,x1,y1], fill=None, outline=(*color, 240), width=5)
        elif shape_type == 'arrow':
            x0,y0,x1,y1 = coords
            draw.line([x0,y0,x1,y1], fill=(*color, 220), width=3)
            # 화살촉
            import math
            angle = math.atan2(y1-y0, x1-x0)
            aw = 12
            for da in [0.5, -0.5]:
                ax = x1 - aw*math.cos(angle-da)
                ay = y1 - aw*math.sin(angle-da)
                draw.line([x1,y1,int(ax),int(ay)], fill=(*color, 220), width=3)
    for x, y, text, color, font_size in labels:
        font = load_font(font_size)
        # 텍스트 배경 박스
        bbox = draw.textbbox((x, y), text, font=font)
        pad = 4
        draw.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad],
                        fill=(0,0,0,160))
        draw.text((x, y), text, fill=(*color, 255), font=font)
    return img

# ─────────────────────────────────────────────
# 1. 뇌 FLAIR - 백질 고신호 (WMH)
# ─────────────────────────────────────────────
def annotate_brain_flair():
    img = Image.open(os.path.join(BASE_2026, "03_brain_FLAIR_WMH.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 좌측 뇌실 주변 백질 고신호 영역
        ('circle', (int(w*0.28), int(h*0.28), int(w*0.42), int(h*0.42)), (255,30,30)),
        # 우측 뇌실 주변 백질 고신호 영역
        ('circle', (int(w*0.55), int(h*0.28), int(w*0.69), int(h*0.42)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.06), "⚠ 뇌 MRI - FLAIR 영상 (이상 소견)", (255,200,50), 20),
        (int(w*0.02), int(h*0.48), "🔴 뇌실 주변 백질에 밝은 점들 관찰", (100,180,255), 16),
        (int(w*0.02), int(h*0.54), "→ 소혈관(가는 혈관)에 미세 혈액순환 장애로", (100,180,255), 15),
        (int(w*0.02), int(h*0.60), "   뇌 조직이 부분적으로 변성된 흔적입니다.", (100,180,255), 15),
        (int(w*0.02), int(h*0.66), "→ 급성 뇌경색(뇌졸중)은 아니며, 경도 소견", (100,180,255), 15),
        (int(w*0.02), int(h*0.72), "→ 고혈압·고지혈증 관리가 중요합니다.", (100,180,255), 15),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_brain_flair.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 2. 뇌 FLAIR 2번 영상 (뇌실 확장)
# ─────────────────────────────────────────────
def annotate_brain_flair2():
    img = Image.open(os.path.join(BASE_2026, "04_brain_FLAIR_WMH2.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 뇌실 주변 백질
        ('rect', (int(w*0.30), int(h*0.35), int(w*0.70), int(h*0.55)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.06), "⚠ 뇌 FLAIR - 뇌실 주변 백질", (255,200,50), 20),
        (int(w*0.02), int(h*0.60), "🔴 뇌실(뇌 중앙 빈 공간) 주변 백질 변화", (100,180,255), 16),
        (int(w*0.02), int(h*0.66), "→ 노화 + 혈압 영향으로 생기는 소혈관 병변", (100,180,255), 15),
        (int(w*0.02), int(h*0.72), "→ Fazekas 등급 1 (경도) - 정기 MRI 추적 권고", (100,180,255), 15),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_brain_flair2.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 3. 심장 스트레인 Bullseye
# ─────────────────────────────────────────────
def annotate_echo_strain():
    img = Image.open(os.path.join(BASE_2026, "05_echo_strain_GLS.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 기저부 하중격막 -1% (분홍/자홍색 분절 - 왼쪽 아래)
        ('circle', (int(w*0.08), int(h*0.52), int(w*0.26), int(h*0.82)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 심장 스트레인 지도 (Bullseye)", (255,200,50), 18),
        (5, int(h*0.86), "🔴 이 부위(-1%): 심장 벽이 거의 수축 안 함!", (255,80,80), 14),
        (5, int(h*0.92), "→ 기저부 하중격막: 국소 수축 기능 저하 의심", (100,180,255), 13),
        (int(w*0.35), int(h*0.04), "전체 스트레인 GS=-11.9%", (255,100,100), 16),
        (int(w*0.35), int(h*0.10), "정상은 -18% 이하여야 함 → 저하!", (100,180,255), 14),
        (int(w*0.35), int(h*0.16), "심장이 눌렸다 펴지는 힘이 약한 상태", (100,180,255), 13),
        (int(w*0.35), int(h*0.22), "→ 심장내과 상담 필요", (100,180,255), 13),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_echo_strain.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 4. 경추 측면 X선 - 일자목
# ─────────────────────────────────────────────
def annotate_cspine():
    img = Image.open(os.path.join(BASE_2026, "06_cspine_lateral.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 경추 전체 영역 - 일직선 경향
        ('rect', (int(w*0.40), int(h*0.20), int(w*0.80), int(h*0.85)), (255,100,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 경추(목뼈) 측면 X선", (255,200,50), 20),
        (int(w*0.02), int(h*0.10), "🔴 정상적인 C자 곡선이 소실됨 (일자목)", (255,80,80), 15),
        (int(w*0.02), int(h*0.16), "→ 정상 목은 앞으로 C자형 곡선이 있어야 함", (100,180,255), 14),
        (int(w*0.02), int(h*0.21), "→ 지금은 직선에 가까워진 상태", (100,180,255), 14),
        (int(w*0.02), int(h*0.26), "→ 장시간 스마트폰·PC 사용이 주원인", (100,180,255), 14),
        (int(w*0.02), int(h*0.31), "→ 목 통증·두통·팔 저림 유발 가능", (100,180,255), 14),
        (int(w*0.02), int(h*0.88), "경도 퇴행성 변화도 동반 관찰됨", (255,200,100), 13),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_cspine.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 5. 경동맥 초음파 - 죽상경화반
# ─────────────────────────────────────────────
def annotate_carotid():
    img = Image.open(os.path.join(BASE_2026, "10_carotid_Rt_bulb_plaque.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 경화반 위치 (중앙 어두운 덩어리)
        ('circle', (int(w*0.28), int(h*0.45), int(w*0.60), int(h*0.75)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 우측 경동맥 초음파 - 죽상경화반", (255,200,50), 17),
        (int(w*0.02), int(h*0.11), "🔴 어두운 덩어리 = 경화반 (혈관벽 기름때)", (255,80,80), 14),
        (int(w*0.02), int(h*0.17), "→ 두께 1.17mm - 경화반 존재 확인!", (255,80,80), 14),
        (int(w*0.02), int(h*0.80), "→ 혈관이 좁아지지는 않았으나", (100,180,255), 13),
        (int(w*0.02), int(h*0.85), "   기름때가 쌓이기 시작한 초기 단계", (100,180,255), 13),
        (int(w*0.02), int(h*0.90), "→ 콜레스테롤·혈압 관리 매우 중요!", (100,180,255), 13),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_carotid.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 6. 요추 측면 X선
# ─────────────────────────────────────────────
def annotate_lspine():
    img = Image.open(os.path.join(BASE_2026, "07_lspine_lateral.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # L4-5, L5-S1 하부 디스크 공간 (하단)
        ('rect', (int(w*0.30), int(h*0.72), int(w*0.80), int(h*0.92)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 요추(허리뼈) 측면 X선", (255,200,50), 20),
        (int(w*0.02), int(h*0.75), "🔴 L4-5, L5-S1 디스크 간격 좁아짐", (255,80,80), 14),
        (int(w*0.02), int(h*0.81), "→ 허리 아래쪽 디스크 닳기 시작", (100,180,255), 14),
        (int(w*0.02), int(h*0.87), "→ 경도 퇴행성 변화, MRI로 정밀 확인 필요", (100,180,255), 13),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_lspine.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 7. 전척추 MRI - 요추 (흉요추 시상면)
# ─────────────────────────────────────────────
def annotate_spine_mri_lumbar():
    img = Image.open(os.path.join(BASE_SPINE, "s005_i012.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 하부 요추 디스크 - 어두운 부분 (오른쪽 아래)
        ('rect', (int(w*0.52), int(h*0.70), int(w*0.85), int(h*0.87)), (255,30,30)),
        # 중간 요추 디스크
        ('rect', (int(w*0.52), int(h*0.56), int(w*0.85), int(h*0.68)), (255,100,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 전척추 MRI - 요추 T2 시상면", (255,200,50), 18),
        (5, int(h*0.58), "🟠L4-5", (255,150,30), 14),
        (5, int(h*0.72), "🔴L5-S1", (255,30,30), 14),
        (int(w*0.02), int(h*0.90), "🔴 검게 변한 디스크 = 수분 소실 (퇴행)", (255,80,80), 13),
        (int(w*0.02), int(h*0.95), "→ 정상 디스크는 밝아야 함. 어두울수록 퇴행 진행", (100,180,255), 12),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_lumbar_mri.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 8. 전척추 MRI - 경추 시상면
# ─────────────────────────────────────────────
def annotate_spine_mri_cervical():
    img = Image.open(os.path.join(BASE_SPINE, "s004_i012.png")).convert("RGBA")
    w, h = img.size
    shapes = [
        # 경추 전체 커브 (직선화)
        ('rect', (int(w*0.30), int(h*0.20), int(w*0.70), int(h*0.85)), (255,100,30)),
        # 경추 중간 디스크 퇴행
        ('circle', (int(w*0.34), int(h*0.48), int(w*0.60), int(h*0.65)), (255,30,30)),
    ]
    labels = [
        (int(w*0.02), int(h*0.04), "⚠ 경추(목) MRI T2 시상면", (255,200,50), 18),
        (int(w*0.02), int(h*0.10), "🔴 목뼈 C자 곡선 소실 (일자목)", (255,80,80), 14),
        (int(w*0.02), int(h*0.16), "→ 정상은 앞으로 볼록한 C자형", (100,180,255), 13),
        (int(w*0.02), int(h*0.21), "🔴 중간 경추부 경도 디스크 퇴행", (255,80,80), 14),
        (int(w*0.02), int(h*0.27), "→ 척수 압박은 없음 (다행)", (100,180,255), 13),
    ]
    result = draw_annotation(img, shapes, labels)
    result = result.convert("RGB")
    result.save(os.path.join(OUT_DIR, "ann_cervical_mri.png"))
    return img_to_b64(result)

# ─────────────────────────────────────────────
# 정상 이미지 (주석 없이)
# ─────────────────────────────────────────────
def load_normal_chest():
    img = Image.open(os.path.join(BASE_2026, "01_chest_AI_normal.png")).convert("RGB")
    return img_to_b64(img)

def load_pwv():
    img = Image.open(os.path.join(BASE_2026, "08_PWV_ABI.png")).convert("RGB")
    return img_to_b64(img)

def load_central_bp():
    img = Image.open(os.path.join(BASE_2026, "09_central_BP.png")).convert("RGB")
    return img_to_b64(img)

# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
print("어노테이션 생성 중...")
b64 = {
    "brain_flair":    annotate_brain_flair(),
    "brain_flair2":   annotate_brain_flair2(),
    "echo_strain":    annotate_echo_strain(),
    "cspine":         annotate_cspine(),
    "carotid":        annotate_carotid(),
    "lspine":         annotate_lspine(),
    "lumbar_mri":     annotate_spine_mri_lumbar(),
    "cervical_mri":   annotate_spine_mri_cervical(),
    "chest_normal":   load_normal_chest(),
    "pwv":            load_pwv(),
    "central_bp":     load_central_bp(),
}
print("완료!")

# HTML 생성
html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>종합 의료영상 분석 보고서 — 남○동 (2026)</title>
<style>
  :root {{
    --red: #e53935;
    --orange: #fb8c00;
    --yellow: #f9a825;
    --green: #43a047;
    --blue: #1565c0;
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text2: #8b949e;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
  }}
  .hero {{
    background: linear-gradient(135deg, #0d1117 0%, #1a2332 50%, #0d2137 100%);
    padding: 48px 24px 36px;
    text-align: center;
    border-bottom: 1px solid var(--border);
  }}
  .hero h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 8px; }}
  .hero .sub {{ color: var(--text2); font-size: 1rem; }}
  .disclaimer {{
    background: #2d2000;
    border: 1px solid #7a5500;
    border-left: 5px solid var(--yellow);
    border-radius: 8px;
    padding: 14px 20px;
    margin: 24px auto;
    max-width: 1100px;
    font-size: 0.9rem;
    color: #ffd54f;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 0 16px 80px; }}

  /* 요약 카드 그리드 */
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
    gap: 14px;
    margin: 28px 0;
  }}
  .summary-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    border-left: 5px solid currentColor;
  }}
  .summary-card.green {{ color: #4caf50; }}
  .summary-card.yellow {{ color: #ffc107; }}
  .summary-card.orange {{ color: #ff9800; }}
  .summary-card.red {{ color: #f44336; }}
  .summary-card h3 {{ font-size: 0.95rem; margin-bottom: 6px; }}
  .summary-card .status {{ font-size: 1.4rem; font-weight: 700; }}
  .summary-card .detail {{ font-size: 0.82rem; color: var(--text2); margin-top: 6px; }}

  /* 섹션 */
  .section {{
    margin: 40px 0;
  }}
  .section-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--border);
  }}
  .section-header h2 {{ font-size: 1.4rem; }}
  .badge {{
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
  }}
  .badge-normal {{ background: #1b3d1c; color: #4caf50; }}
  .badge-caution {{ background: #3d2c00; color: #ff9800; }}
  .badge-warning {{ background: #3d0d0d; color: #f44336; }}
  .badge-mild {{ background: #2c2800; color: #ffc107; }}

  /* 이미지+설명 레이아웃 */
  .finding {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    margin: 20px 0;
  }}
  .finding-header {{
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .finding-header h3 {{ font-size: 1.1rem; }}
  .finding-body {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }}
  @media (max-width: 700px) {{ .finding-body {{ grid-template-columns: 1fr; }} }}
  .finding-img {{
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    border-right: 1px solid var(--border);
  }}
  .finding-img img {{
    max-width: 100%;
    max-height: 380px;
    object-fit: contain;
    border-radius: 8px;
  }}
  .finding-img-full {{
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }}
  .finding-img-full img {{
    max-width: 100%;
    max-height: 280px;
    object-fit: contain;
    border-radius: 8px;
  }}
  .finding-text {{
    padding: 20px 22px;
  }}
  .finding-text h4 {{
    font-size: 0.95rem;
    color: var(--text2);
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* 항목 설명 */
  .item {{ margin: 10px 0; }}
  .item-label {{
    font-size: 0.8rem;
    color: var(--text2);
    margin-bottom: 2px;
  }}
  .item-value {{
    font-size: 1rem;
    font-weight: 600;
  }}
  .item-value.abnormal {{ color: #f44336; }}
  .item-value.caution {{ color: #ff9800; }}
  .item-value.mild {{ color: #ffc107; }}
  .item-value.normal {{ color: #4caf50; }}

  .explain {{
    background: #0d1f3d;
    border-left: 3px solid #1565c0;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 14px 0;
    font-size: 0.88rem;
    color: #90caf9;
  }}
  .explain strong {{ color: #64b5f6; display: block; margin-bottom: 4px; }}

  .warn-box {{
    background: #3d0d0d;
    border: 1px solid #f44336;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 14px 0;
    font-size: 0.88rem;
    color: #ef9a9a;
  }}
  .warn-box strong {{ color: #f44336; display: block; margin-bottom: 4px; }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 0.88rem;
  }}
  th {{ background: #1f2937; color: var(--text2); padding: 8px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); }}
  td.ab {{ color: #f44336; font-weight: 600; }}
  td.ca {{ color: #ff9800; font-weight: 600; }}
  td.ok {{ color: #4caf50; }}

  .two-imgs {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }}
  @media (max-width: 700px) {{ .two-imgs {{ grid-template-columns: 1fr; }} }}

  /* 정상 섹션 */
  .normal-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin: 16px 0;
  }}
  .normal-card {{
    background: var(--card);
    border: 1px solid #1b3d1c;
    border-radius: 12px;
    overflow: hidden;
  }}
  .normal-card-header {{
    background: #0a1f0b;
    padding: 12px 16px;
    font-size: 0.9rem;
    color: #4caf50;
    font-weight: 600;
  }}
  .normal-card img {{
    width: 100%;
    max-height: 200px;
    object-fit: contain;
    background: #000;
    display: block;
  }}
  .normal-card-body {{ padding: 12px 16px; font-size: 0.85rem; color: var(--text2); }}

  .action-list {{ list-style: none; }}
  .action-list li {{
    padding: 10px 14px;
    border-left: 3px solid var(--orange);
    background: #1a1500;
    margin: 8px 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.9rem;
  }}
  .action-list li strong {{ color: #ffa726; }}

  footer {{
    text-align: center;
    padding: 32px 16px;
    border-top: 1px solid var(--border);
    color: var(--text2);
    font-size: 0.85rem;
  }}
</style>
</head>
<body>

<div class="hero">
  <h1>🏥 종합 의료영상 분석 보고서</h1>
  <div class="sub">
    남○동 (58세, 남) · 키 181cm · 체중 85kg · BMI 26.4<br>
    <strong>2026-02-13 검진</strong> (필메디스의원) + <strong>2026-07-06 전척추 MRI</strong>
  </div>
</div>

<div class="container">

<div class="disclaimer">
  ⚠️ <strong>중요 안내:</strong> 본 문서는 DICOM 데이터 기반의 <u>참고용 정리 자료</u>입니다.
  실제 진단 및 치료 결정은 반드시 <strong>담당 전문의의 공식 판독</strong>을 따르시기 바랍니다.
</div>

<!-- ============ 요약 카드 ============ -->
<div class="section">
  <div class="section-header">
    <h2>📊 한눈에 보는 종합 결과</h2>
  </div>
  <div class="summary-grid">
    <div class="summary-card green">
      <h3>흉부 X선</h3>
      <div class="status">✅ 정상</div>
      <div class="detail">AI 이상소견 없음. 폐·심장 모양 정상</div>
    </div>
    <div class="summary-card yellow">
      <h3>경추(목뼈) X선 + MRI</h3>
      <div class="status">🟡 경미 이상</div>
      <div class="detail">일자목(C커브 소실) + 경도 퇴행성 변화</div>
    </div>
    <div class="summary-card yellow">
      <h3>요추(허리) MRI</h3>
      <div class="status">🟠 주의</div>
      <div class="detail">L4-5, L5-S1 디스크 퇴행·팽윤, 경도 협착</div>
    </div>
    <div class="summary-card yellow">
      <h3>뇌 MRI</h3>
      <div class="status">🟡 경미 이상</div>
      <div class="detail">뇌실 주변 소혈관 변화(경도). 급성 병변 없음</div>
    </div>
    <div class="summary-card orange">
      <h3>경동맥 초음파</h3>
      <div class="status">🟠 주의</div>
      <div class="detail">양측 죽상경화반(혈관 기름때) 존재. 협착 無</div>
    </div>
    <div class="summary-card orange">
      <h3>심장 초음파</h3>
      <div class="status">🟠 주의</div>
      <div class="detail">GLS -11.9% (심장 수축력 저하). EF 59% 정상</div>
    </div>
    <div class="summary-card yellow">
      <h3>혈관경직도(PWV)</h3>
      <div class="status">🟡 경계역</div>
      <div class="detail">baPWV ~1,380 cm/s. 경계 수준</div>
    </div>
    <div class="summary-card green">
      <h3>중심혈압</h3>
      <div class="status">✅ 정상</div>
      <div class="detail">중심수축기압 114mmHg. 정상 범위</div>
    </div>
  </div>
</div>

<!-- ============ 비정상 소견 ============ -->
<div class="section">
  <div class="section-header">
    <h2>🔴 비정상·주의 소견 (상세 분석)</h2>
  </div>

  <!-- 1. 경동맥 -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #ff9800;">
      <span style="font-size:1.6rem">🫀</span>
      <h3>1. 경동맥 죽상경화반 (Carotid Atherosclerotic Plaque)</h3>
      <span class="badge badge-caution">🟠 주의</span>
    </div>
    <div class="finding-body">
      <div class="finding-img">
        <img src="data:image/png;base64,{b64['carotid']}" alt="경동맥 초음파 어노테이션">
      </div>
      <div class="finding-text">
        <h4>측정값</h4>
        <table>
          <tr><th>측정 부위</th><th>우측</th><th>좌측</th><th>판정</th></tr>
          <tr><td>CCA 내중막두께(IMT)</td><td class="ca">0.76mm</td><td>0.73mm</td><td>경계역</td></tr>
          <tr><td>CCA 경화반</td><td class="ab">1.16mm</td><td class="ca">0.92mm</td><td class="ab">경화반 존재</td></tr>
          <tr><td>경동맥구(Bulb) 경화반</td><td class="ab">1.46mm</td><td class="ab">1.26mm</td><td class="ab">양측 경화반</td></tr>
          <tr><td>내경동맥(ICA) 경화반</td><td class="ab">1.52mm</td><td>-</td><td class="ab">우측 경화반</td></tr>
          <tr><td>혈류 속도(PSV)</td><td class="ok">49cm/s</td><td class="ok">48cm/s</td><td class="ok">정상</td></tr>
        </table>
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          목 양쪽에는 뇌로 피를 공급하는 <strong>경동맥</strong>이 있습니다.<br>
          이 혈관 안쪽 벽에 <strong>콜레스테롤과 지방이 쌓여 딱딱해진 덩어리</strong>(경화반)가 발견되었습니다.<br>
          마치 오래된 수도관에 녹이 쌓이는 것과 같습니다.<br>
          아직 혈관이 막히지는 않았지만, <strong>장기간 방치하면 뇌졸중 위험</strong>이 높아집니다.
        </div>
        <div class="warn-box">
          <strong>⚠️ 권고사항</strong>
          콜레스테롤 수치 측정 → 필요 시 약물 치료 상담<br>
          혈압 철저 관리 / 금연 / 저염식 / 규칙적 유산소 운동<br>
          <strong>매년 경동맥 초음파 추적 검사</strong> 강력 권고
        </div>
      </div>
    </div>
  </div>

  <!-- 2. 심장 스트레인 -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #f44336;">
      <span style="font-size:1.6rem">💓</span>
      <h3>2. 심장 초음파 — 전체 종축 스트레인(GLS) 저하</h3>
      <span class="badge badge-caution">🟠 주의</span>
    </div>
    <div class="finding-body">
      <div class="finding-img">
        <img src="data:image/png;base64,{b64['echo_strain']}" alt="심장 스트레인 불아이">
      </div>
      <div class="finding-text">
        <h4>심초음파 측정값</h4>
        <table>
          <tr><th>항목</th><th>측정값</th><th>정상기준</th><th>판정</th></tr>
          <tr><td>좌심실 구혈률(EF)</td><td class="ok">59%</td><td>≥52%</td><td class="ok">정상</td></tr>
          <tr><td><strong>전체 종축 스트레인(GLS)</strong></td><td class="ab">-11.9%</td><td>≤-18~-20%</td><td class="ab">⚠ 저하!</td></tr>
          <tr><td>기저부 하중격막 분절</td><td class="ab">-1%</td><td>-15% 이상</td><td class="ab">국소 저하</td></tr>
          <tr><td>좌심방용적지수(LAVI)</td><td class="ca">36.4 ml/m²</td><td>&lt;34</td><td class="ca">경도 증가</td></tr>
          <tr><td>E/E′ (충만압)</td><td class="ok">4.1</td><td>&lt;8</td><td class="ok">정상</td></tr>
        </table>
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          심장은 수축할 때 길이 방향으로 줄어들어야 합니다. 이 <strong>수축하는 힘을 "스트레인"</strong>으로 측정합니다.<br><br>
          • 정상: -18% 이하(더 음수일수록 좋음)<br>
          • 현재: <strong>-11.9% → 심장 수축력이 많이 약함</strong><br><br>
          겉으로 보이는 "구혈률(EF)"은 59%로 정상이지만, 더 정밀한 검사에서 이상이 드러났습니다.<br>
          왼쪽 아래 분절(-1%)은 거의 수축하지 않는 것으로 나타났습니다.
        </div>
        <div class="warn-box">
          <strong>⚠️ 권고사항</strong>
          <strong>심장내과 전문의 상담 강력 권고</strong><br>
          혈압·혈당·지질 수치 검사 및 관리<br>
          과도한 음주·흡연 금지 / 규칙적 유산소 운동<br>
          필요 시 심장 MRI 또는 심근관류검사(핵의학) 추가 고려
        </div>
      </div>
    </div>
  </div>

  <!-- 3. 뇌 백질 변화 -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #ffc107;">
      <span style="font-size:1.6rem">🧠</span>
      <h3>3. 뇌 MRI — 백질 소혈관 허혈성 변화</h3>
      <span class="badge badge-mild">🟡 경미 이상</span>
    </div>
    <div class="finding-body">
      <div class="two-imgs">
        <div class="finding-img-full">
          <img src="data:image/png;base64,{b64['brain_flair']}" alt="뇌 FLAIR 1">
        </div>
        <div class="finding-img-full">
          <img src="data:image/png;base64,{b64['brain_flair2']}" alt="뇌 FLAIR 2">
        </div>
      </div>
      <div class="finding-text" style="grid-column: 1 / -1;">
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          MRI FLAIR 영상에서 <strong>뇌 안쪽 뇌실 주변에 밝은 점(고신호)들이 관찰</strong>됩니다.<br><br>
          이는 뇌 속 <strong>아주 가는 혈관들(소혈관)에 미세한 혈액순환 장애</strong>가 생긴 흔적입니다.<br>
          쉽게 말해 <strong>"뇌 안에 아주 작은 상처들"</strong>이 있는 것으로 볼 수 있습니다.<br><br>
          • 급성 뇌경색(뇌졸중)은 아닙니다 — 출혈·종양도 없음<br>
          • Fazekas 등급 1 (경도) — 58세 연령에서 드물지 않은 소견<br>
          • 고혈압이 있으면 더 빨리 진행할 수 있어 <strong>혈압 관리가 매우 중요</strong>합니다
        </div>
        <div class="warn-box">
          <strong>⚠️ 권고사항</strong>
          혈압 목표: 130/80 mmHg 미만 유지<br>
          1~2년마다 뇌 MRI 추적 검사 권고<br>
          두통·어지럼증·기억력 저하 심해지면 즉시 신경과 방문
        </div>
      </div>
    </div>
  </div>

  <!-- 4. 요추 디스크 MRI -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #ff9800;">
      <span style="font-size:1.6rem">🦴</span>
      <h3>4. 하부 요추 퇴행성 디스크질환 (전척추 MRI)</h3>
      <span class="badge badge-caution">🟠 주의 (주 소견)</span>
    </div>
    <div class="finding-body">
      <div class="finding-img">
        <img src="data:image/png;base64,{b64['lumbar_mri']}" alt="요추 MRI 어노테이션">
      </div>
      <div class="finding-text">
        <h4>주요 소견</h4>
        <div class="item">
          <div class="item-label">디스크 수분소실(Desiccation)</div>
          <div class="item-value abnormal">L4-5, L5-S1 — 검게 변함 (퇴행)</div>
        </div>
        <div class="item">
          <div class="item-label">디스크 간격 협소</div>
          <div class="item-value caution">하부 요추 높이 감소</div>
        </div>
        <div class="item">
          <div class="item-label">후방 팽윤/돌출</div>
          <div class="item-value caution">경막낭 경도 압박</div>
        </div>
        <div class="item">
          <div class="item-label">척수 압박·종양</div>
          <div class="item-value normal">없음 ✅</div>
        </div>
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          허리뼈 사이에는 충격을 흡수하는 <strong>디스크(추간판)</strong>가 있습니다.<br>
          정상 디스크는 MRI에서 <strong>밝게(수분이 풍부)</strong> 보입니다.<br><br>
          현재 허리 아래쪽(L4-5, L5-S1)의 디스크가 <strong>검게(어둡게)</strong> 변해 있습니다.<br>
          → 디스크가 <strong>말라서 납작해지고 뒤로 삐져나온 상태</strong>입니다.<br><br>
          신경을 심하게 누르지는 않지만, 허리 통증·다리 저림의 원인이 될 수 있습니다.
        </div>
        <div class="warn-box">
          <strong>⚠️ 권고사항</strong>
          척추 전문의(정형외과/신경외과) 상담<br>
          코어 근육 강화 운동 / 올바른 자세 습관<br>
          무거운 물건 들기 자제 / 오래 앉기 금지<br>
          통증 심할 시 물리치료·주사치료 고려
        </div>
      </div>
    </div>
  </div>

  <!-- 5. 경추 일자목 -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #ffc107;">
      <span style="font-size:1.6rem">🦴</span>
      <h3>5. 경추(목뼈) — 정상만곡 소실(일자목) + 경도 퇴행성 변화</h3>
      <span class="badge badge-mild">🟡 경미 이상</span>
    </div>
    <div class="finding-body">
      <div class="two-imgs">
        <div class="finding-img-full">
          <img src="data:image/png;base64,{b64['cspine']}" alt="경추 X선 어노테이션">
        </div>
        <div class="finding-img-full">
          <img src="data:image/png;base64,{b64['cervical_mri']}" alt="경추 MRI 어노테이션">
        </div>
      </div>
      <div class="finding-text" style="grid-column: 1 / -1;">
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          정상적인 목뼈는 <strong>앞으로 볼록한 'C'자 모양</strong>이어야 합니다.<br>
          현재 목뼈가 <strong>거의 직선</strong>이 되어 있습니다 (일자목 / 거북목).<br><br>
          이 상태가 지속되면:<br>
          • 목·어깨 통증 및 뻐근함<br>
          • 두통, 집중력 저하<br>
          • 팔·손 저림 (심해지면)<br><br>
          MRI에서 척수(신경줄기)를 누르는 심한 압박은 없습니다 (다행).
        </div>
        <div class="warn-box">
          <strong>⚠️ 권고사항</strong>
          스마트폰·PC 사용 시간 줄이기, 모니터 눈높이 조정<br>
          목 스트레칭·강화 운동 꾸준히 실시<br>
          목 통증·팔 저림 심해지면 척추 전문의 상담
        </div>
      </div>
    </div>
  </div>

  <!-- 6. PWV 경계역 -->
  <div class="finding">
    <div class="finding-header" style="border-left: 5px solid #ffc107;">
      <span style="font-size:1.6rem">🩺</span>
      <h3>6. 혈관 경직도(PWV) 경계역 + 과체중</h3>
      <span class="badge badge-mild">🟡 경계역</span>
    </div>
    <div class="finding-body">
      <div class="finding-img">
        <img src="data:image/png;base64,{b64['pwv']}" alt="PWV 리포트">
      </div>
      <div class="finding-text">
        <table>
          <tr><th>항목</th><th>수치</th><th>판정</th></tr>
          <tr><td>baPWV 우측</td><td class="ca">1,396 cm/s</td><td class="ca">경계역</td></tr>
          <tr><td>baPWV 좌측</td><td class="ca">1,369 cm/s</td><td class="ca">경계역</td></tr>
          <tr><td>ABI (말초동맥)</td><td class="ok">1.12</td><td class="ok">정상</td></tr>
          <tr><td>BMI</td><td class="ca">26.4 (과체중)</td><td class="ca">관리 필요</td></tr>
        </table>
        <div class="explain">
          <strong>🔵 일반인을 위한 설명</strong>
          PWV는 <strong>혈관의 딱딱한 정도</strong>를 측정합니다.<br>
          혈관이 딱딱해질수록 심장이 더 일을 많이 해야 하고, 심뇌혈관 질환 위험이 높아집니다.<br><br>
          현재 수치는 <strong>경계선상</strong>입니다(1,400 이상이 이상, 현재 1,380 수준).<br>
          체중 감량 시 혈관 경직도가 개선될 수 있습니다.
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ============ 정상 소견 ============ -->
<div class="section">
  <div class="section-header">
    <h2>✅ 정상 소견</h2>
    <span class="badge badge-normal">안심 가능</span>
  </div>
  <div class="normal-grid">
    <div class="normal-card">
      <div class="normal-card-header">✅ 흉부 X선 — AI 판독 정상</div>
      <img src="data:image/png;base64,{b64['chest_normal']}" alt="흉부 X선">
      <div class="normal-card-body">
        AI(Lunit) 이상 점수: Low 5. 양측 폐 깨끗, 심비대 없음, 결핵 의심 없음.
        폐암·폐렴·흉막삼출 소견 없음.
      </div>
    </div>
    <div class="normal-card">
      <div class="normal-card-header">✅ 중심혈압 — 정상</div>
      <img src="data:image/png;base64,{b64['central_bp']}" alt="중심혈압">
      <div class="normal-card-body">
        중심수축기압 114mmHg (정상). ABI 1.12 — 다리 혈관 막힘 없음.
        말초동맥질환(하지 혈관 협착) 없음.
      </div>
    </div>
    <div class="normal-card">
      <div class="normal-card-header">✅ 뇌 MRI — 급성 병변 없음</div>
      <div style="background:#111;padding:16px;text-align:center;color:#4caf50;font-size:2rem">🧠✅</div>
      <div class="normal-card-body">
        확산강조영상(DWI): 급성 뇌경색 없음.<br>
        T2* : 미세출혈 없음.<br>
        종양·중심선 편위 없음. 뇌간·소뇌 정상.
      </div>
    </div>
    <div class="normal-card">
      <div class="normal-card-header">✅ 흉추 — 정상</div>
      <div style="background:#111;padding:16px;text-align:center;color:#4caf50;font-size:2rem">🦴✅</div>
      <div class="normal-card-body">
        흉추 디스크 높이·신호 양호.<br>
        척수·척추관 정상. 유의 협착·탈출 없음.<br>
        압박골절·전이·감염 없음.
      </div>
    </div>
  </div>
</div>

<!-- ============ 종합 행동 권고 ============ -->
<div class="section">
  <div class="section-header">
    <h2>🎯 종합 행동 권고</h2>
  </div>
  <div class="finding" style="border: 1px solid #ff9800;">
    <div class="finding-header" style="border-left: 5px solid #ff9800;">
      <h3>즉시 또는 단기간 내 해야 할 일</h3>
    </div>
    <div style="padding: 20px;">
      <ul class="action-list">
        <li><strong>심장내과 상담 (최우선):</strong> GLS 저하·경동맥 경화반 → 심혈관 위험도 종합 평가. 필요 시 지질강하제(스타틴) 처방 논의</li>
        <li><strong>혈액검사:</strong> 공복혈당·당화혈색소(HbA1c)·LDL 콜레스테롤·중성지방·hsCRP 확인</li>
        <li><strong>척추 전문의 상담:</strong> 요추 L4-5/L5-S1 디스크 퇴행 — 현재 증상 및 치료 계획 수립</li>
        <li><strong>체중 감량 목표:</strong> 현 85kg → 75~78kg 목표 (BMI 22~24). 심혈관 지표 전반 개선 기대</li>
        <li><strong>규칙적 유산소 운동:</strong> 주 5회 30~45분 빠르게 걷기 / 자전거 / 수영. 척추에 무리 없는 운동 선택</li>
      </ul>
    </div>
  </div>
  <div class="finding" style="border: 1px solid #1565c0; margin-top: 16px;">
    <div class="finding-header" style="border-left: 5px solid #1565c0;">
      <h3>정기 추적 검사 계획</h3>
    </div>
    <div style="padding: 20px;">
      <table>
        <tr><th>시기</th><th>검사</th><th>이유</th></tr>
        <tr><td>6개월 후</td><td>혈액검사 (지질·혈당), 혈압 모니터링</td><td>생활습관 개선 효과 확인</td></tr>
        <tr><td>1년 후</td><td>경동맥 초음파, 심장 초음파(스트레인 포함)</td><td>경화반 진행·심장 기능 추적</td></tr>
        <tr><td>1~2년 후</td><td>뇌 MRI (FLAIR 포함)</td><td>백질 소혈관 변화 추적</td></tr>
        <tr><td>증상 시</td><td>척추 전문의 방문</td><td>요추 디스크 증상 악화 시</td></tr>
      </table>
    </div>
  </div>
</div>

</div><!-- /container -->

<footer>
  <p>⚕️ 본 보고서는 DICOM 영상 데이터 기반 참고 자료입니다 | 최종 진단은 담당 전문의에게</p>
  <p style="margin-top:8px;font-size:0.75rem">생성일: 2026-07-09 | 검진일: 2026-02-13 (종합검진) + 2026-07-06 (전척추 MRI)</p>
</footer>

</body>
</html>"""

OUT_HTML = r"D:\남기동\수원\data\필메디스_통합보고서\종합의료영상_분석보고서.html"
os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"HTML 보고서 생성 완료: {OUT_HTML}")
print(f"어노테이션 이미지 폴더: {OUT_DIR}")
