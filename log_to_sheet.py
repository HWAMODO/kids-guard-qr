import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz
import streamlit as st

# 🔐 인증 키 로딩 및 복원
raw_secrets = dict(st.secrets["gcp_service_account"])
raw_secrets["private_key"] = raw_secrets["private_key"].replace("\\n", "\n")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(raw_secrets, scope)
client = gspread.authorize(credentials)

sheet = client.open("체크인기록").worksheet("Sheet1")

# ✅ 헤더 검사
def check_header():
    expected = ["연번", "이름", "근무장소", "근무시간"]
    actual = sheet.row_values(1)
    if actual != expected:
        sheet.delete_row(1)
        sheet.insert_row(expected, index=1)

# ✅ 연번 계산
def get_next_serial_number():
    all_data = sheet.get_all_values()
    return len(all_data)  # 헤더 포함

# ✅ 시간 함수 (KST 기준)
def get_kst_now():
    try:
        kst = pytz.timezone("Asia/Seoul")
        return datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")

# ✅ 체크인 함수 (checkin_form.py에서 호출)
def log_checkin(name, school):
    check_header()
    serial = get_next_serial_number()
    now = get_kst_now()

    new_row = [serial, name, school, now]
    if len(new_row) == 4:
        sheet.append_row(new_row, value_input_option="RAW")
