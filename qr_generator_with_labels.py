# qr_generator_with_labels.py
import qrcode
from PIL import Image, ImageDraw, ImageFont
import os

# 🔗 Streamlit 앱 기본 URL
BASE_URL = "http://localhost:8501"  # 배포 시에는 Cloud 주소로 변경

# 📚 수서경찰서 관할 초등학교 전체 26개교
schools = [
    "대도초", "언주초", "도성초", "역삼초",       # 도곡지구대
    "도곡초", "대현초", "대곡초", "대치초",       # 대치지구대
    "율현초", "왕북초", "세명초", "수서초", "자곡초", "대왕초",   # 대왕파출소
    "일원초", "개포초", "대모초", "양전초", "대진초", "영희초", "대청초",  # 일원지구대
    "개일초", "포이초", "개원초", "개현초", "구룡초"    # 개포지구대
]

# 📂 QR 코드 저장 폴더
output_dir = "qr_codes"
os.makedirs(output_dir, exist_ok=True)

# 🖋️ 폰트 설정
try:
    font = ImageFont.truetype("malgun.ttf", 20)  # Windows: 맑은 고딕
except:
    font = ImageFont.load_default()

for school in schools:
    # URL 생성
    url = f"{BASE_URL}/?school={school}"

    # QR 코드 생성
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # 캔버스 확장 (아래쪽에 텍스트 공간 추가)
    w, h = qr_img.size
    new_h = h + 40
    canvas = Image.new("RGB", (w, new_h), "white")
    canvas.paste(qr_img, (0, 0))

    # 텍스트 그리기
    draw = ImageDraw.Draw(canvas)
    text = school
    # ✅ Pillow 최신버전: textbbox로 글자 크기 구하기
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - text_w) / 2, h + 5), text, font=font, fill="black")

    # 파일 저장
    filename = f"{output_dir}/{school}_QR.png"
    canvas.save(filename, "PNG")
    print(f"✅ {school} QR 생성 완료 → {filename}")

print("🎉 모든 학교 QR 코드 생성 완료")
