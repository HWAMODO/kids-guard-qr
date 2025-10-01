# qr_generator_with_labels.py — 아동안전지킴이 전용 QR 생성기 (라벨 포함)
# 생성 규격: ?page=대원 체크인&school=...&name=...&note=...

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from datetime import datetime

# 🔗 Streamlit 앱 기본 URL (배포 주소) — 실제 주소 고정
BASE_URL = "https://kids-guard-qr-stygvpcrmtgek4s4zrpbee.streamlit.app"

# 🏫 수서경찰서 관내 초등학교 26개 (streamlit 앱과 동일 명칭)
SCHOOLS = [
    "개원초등학교","개일초등학교","개포초등학교","개현초등학교","구룡초등학교",
    "논현초등학교","대곡초등학교","대도초등학교","대모초등학교","대왕초등학교",
    "대진초등학교","대청초등학교","대치초등학교","대현초등학교","도곡초등학교",
    "도성초등학교","봉은초등학교","삼릉초등학교","세명초등학교","수서초등학교",
    "신구초등학교","압구정초등학교","양전초등학교","언북초등학교","언주초등학교",
    "율현초등학교",
]

# ✏️ (선택) 공통 프리필 값 — 이름/특이사항을 미리 박아 QR 생성하고 싶으면 입력
PRESET_NAME = ""   # 예: "홍길동"
PRESET_NOTE = ""   # 예: "통학로 이상 없음"

# 📂 출력 폴더
OUTPUT_DIR = "qr_codes"

# 🖋️ 폰트 설정 (Windows: 맑은 고딕 / 환경별 폴백)
def _load_font(size=20):
    try:
        return ImageFont.truetype("malgun.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("Arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

FONT = _load_font(20)

def build_checkin_url(base_url: str, school: str, name: str = "", note: str = "") -> str:
    """
    Streamlit 대원 체크인 페이지로 바로 연결되는 URL 생성.
    한글 파라미터를 안전하게 UTF-8 인코딩한다.
    """
    params = {
        "page": "대원 체크인",
        "school": school,
        "name": name,
        "note": note,
    }

    parsed = urlparse(base_url)
    existing_q = dict(parse_qsl(parsed.query))
    existing_q.update(params)

    # UTF-8 안전 인코딩
    new_q = urlencode(existing_q, doseq=False, encoding="utf-8")
    link = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))
    return link

def sanitize_filename(text: str) -> str:
    """파일명 안전화(Windows 예약문자 제거, 공백→_ 치환)."""
    bad = '<>:"/\\|?*'
    for ch in bad:
        text = text.replace(ch, "")
    return text.replace(" ", "_")

def make_qr_with_label(url: str, label_text: str, out_path: str, box_size=10, border=4):
    """URL로 QR 생성하고 하단에 라벨(학교명) 텍스트를 그려 PNG 저장."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    w, h = qr_img.size
    label_pad = 44  # 라벨 영역
    canvas = Image.new("RGB", (w, h + label_pad), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), label_text, font=FONT)  # Pillow 8.0+
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2, h + (label_pad - th) / 2), label_text, font=FONT, fill="black")

    canvas.save(out_path, "PNG")

def main():
    # 출력 폴더 초기화(기존 파일 제거)
    if os.path.exists(OUTPUT_DIR):
        for f in os.listdir(OUTPUT_DIR):
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception:
                pass
    else:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"🔗 BASE_URL = {BASE_URL}")
    print(f"🏷️ PRESET name='{PRESET_NAME}', note='{PRESET_NOTE}'")
    print(f"📁 출력 경로: {os.path.abspath(OUTPUT_DIR)}")

    # 생성 내역 CSV
    manifest_path = os.path.join(OUTPUT_DIR, "qr_manifest.csv")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        mf.write("generated_at,school,url\n")

    for school in SCHOOLS:
        url = build_checkin_url(BASE_URL, school, PRESET_NAME, PRESET_NOTE)
        print(url)  # 콘솔 확인
        safe_school = sanitize_filename(school)
        filename = f"{OUTPUT_DIR}/{safe_school}_QR.png"
        make_qr_with_label(url, school, filename)

        with open(manifest_path, "a", encoding="utf-8") as mf:
            mf.write(f"{datetime.now().isoformat(timespec='seconds')},{school},{url}\n")

        print(f"✅ {school} QR 생성 완료 → {filename}")

    print("🎉 모든 학교 QR 코드 생성 완료")

if __name__ == "__main__":
    main()
