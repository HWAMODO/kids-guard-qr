# streamlit_app.py — 아동안전지킴이 전용 (수서경찰서 관내 초등학교 26개 목록)
import streamlit as st
from datetime import datetime, date
import pytz
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
import qrcode
from io import BytesIO

SEOUL_TZ = pytz.timezone("Asia/Seoul")

# ------------------------------
# 수서경찰서 관내 초등학교 목록 (26개)
# ------------------------------
SCHOOL_OPTIONS = [
    "개원초등학교","개일초등학교","개포초등학교","개현초등학교","구룡초등학교",
    "논현초등학교","대곡초등학교","대도초등학교","대모초등학교","대왕초등학교",
    "대진초등학교","대청초등학교","대치초등학교","대현초등학교","도곡초등학교",
    "도성초등학교","봉은초등학교","삼릉초등학교","세명초등학교","수서초등학교",
    "신구초등학교","압구정초등학교","양전초등학교","언북초등학교","언주초등학교",
    "율현초등학교"
]

# ------------------------------
# Secrets & GSpread 연결
# ------------------------------
def _find_service_account_dict():
    for k in ["gcp_service_account", "google_service_account", "service_account"]:
        if k in st.secrets:
            return st.secrets[k]
    st.stop()

def _find_spreadsheet_info():
    spreadsheet_id = None
    worksheet_name = "checkins_kids"

    if "gsheet" in st.secrets:
        spreadsheet_id = st.secrets["gsheet"].get("spreadsheet_id", spreadsheet_id)
        worksheet_name = st.secrets["gsheet"].get("worksheet_name", worksheet_name)

    if not spreadsheet_id:
        spreadsheet_id = st.secrets.get("spreadsheet_id", spreadsheet_id)
    if "worksheet_name" in st.secrets:
        worksheet_name = st.secrets.get("worksheet_name", worksheet_name)

    if not spreadsheet_id:
        st.stop()
    return spreadsheet_id, worksheet_name

@st.cache_resource(show_spinner=False)
def get_worksheet():
    sa_dict = _find_service_account_dict()
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_dict, scope)
    gc = gspread.authorize(creds)
    spreadsheet_id, worksheet_name = _find_spreadsheet_info()
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        ws.append_row(["timestamp_kst","type","name","school","note"])
    return ws

def append_checkin(row):
    ws = get_worksheet()
    ws.append_row(row)

def fetch_all_records_df():
    ws = get_worksheet()
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    if "timestamp_kst" in df.columns:
        df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"], errors="coerce")
    return df

# ------------------------------
# 기본 UI
# ------------------------------
st.set_page_config(page_title="아동안전지킴이 QR 체크인", page_icon="✅", layout="wide")
st.title("아동안전지킴이 QR 체크인")
st.caption("수서경찰서 관내 초등학교 전용 시스템")

# ------------------------------
# 쿼리파라미터
# ------------------------------
def get_query_params():
    try:
        qp = dict(st.query_params)
        return {k:(v[0] if isinstance(v,list) else v) for k,v in qp.items()}
    except Exception:
        qp = st.experimental_get_query_params()
        return {k:(v[0] if isinstance(v,list) else v) for k,v in qp.items()}

PAGES = ["대원 체크인","관리자 요약","QR 생성기"]
qp = get_query_params()
default_index = PAGES.index(qp["page"]) if "page" in qp and qp["page"] in PAGES else 0
page = st.sidebar.radio("페이지 선택", PAGES, index=default_index)

# ------------------------------
# 페이지 1: 대원 체크인
# ------------------------------
if page == "대원 체크인":
    st.subheader("대원 체크인")
    with st.form("checkin_form"):
        col1,col2 = st.columns(2)
        with col1:
            name = st.text_input("이름", value=qp.get("name",""), placeholder="홍길동")
            school = st.selectbox("학교", SCHOOL_OPTIONS, index=SCHOOL_OPTIONS.index(qp["school"]) if qp.get("school") in SCHOOL_OPTIONS else 0)
        with col2:
            note = st.text_area("특이사항", value=qp.get("note",""), placeholder="예) 통학로 상황 양호, 주변 공원 인원 증가 등", height=88)
            now_kst = datetime.now(SEOUL_TZ)
            st.info(f"기록 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
        submitted = st.form_submit_button("체크인 기록")
        if submitted:
            if not name.strip():
                st.warning("이름은 필수 입력입니다.")
                st.stop()
            row = [datetime.now(SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S"),"아동안전지킴이",name.strip(),school,note.strip()]
            append_checkin(row)
            st.success(f"체크인 완료: 아동안전지킴이 · {name} · {school}")
            st.toast("기록되었습니다.", icon="✅")

# ------------------------------
# 페이지 2: 관리자 요약
# ------------------------------
elif page == "관리자 요약":
    st.subheader("관리자 요약")
    df = fetch_all_records_df()
    if df.empty:
        st.info("아직 기록이 없습니다.")
    else:
        with st.expander("필터", expanded=True):
            c1,c2,c3 = st.columns(3)
            with c1:
                start_d = st.date_input("시작일", value=df["timestamp_kst"].min().date())
            with c2:
                end_d = st.date_input("종료일", value=df["timestamp_kst"].max().date())
        fdf = df[(df["timestamp_kst"].dt.date>=start_d)&(df["timestamp_kst"].dt.date<=end_d)]
        st.metric("총 체크인 수", len(fdf))
        st.dataframe(fdf.sort_values("timestamp_kst", ascending=False), use_container_width=True)
        csv = fdf.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSV 다운로드", data=csv, file_name="checkins_kids.csv", mime="text/csv")

# ------------------------------
# 페이지 3: QR 생성기
# ------------------------------
elif page == "QR 생성기":
    st.subheader("QR 생성기 (아동안전지킴이 전용)")
    base_url = st.text_input("배포된 앱의 공개 URL", placeholder="예) https://your-app-name.streamlit.app/")
    c1,c2 = st.columns(2)
    with c1:
        school = st.selectbox("학교", SCHOOL_OPTIONS)
    with c2:
        name = st.text_input("이름", placeholder="홍길동")
        note = st.text_input("특이사항(선택)", placeholder="예) 통학로 상태 양호")
    if st.button("QR 생성"):
        if not base_url.strip():
            st.warning("앱 URL을 입력하세요.")
            st.stop()
        params = {"page":"대원 체크인","name":name,"school":school,"note":note}
        parsed = urlparse(base_url)
        existing_q = dict(parse_qsl(parsed.query))
        existing_q.update(params)
        new_q = urlencode(existing_q, doseq=False, encoding="utf-8")
        link = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))
        st.code(link, language="text")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="체크인 QR", use_column_width=False)
        st.download_button("QR 이미지 다운로드", data=buf.getvalue(), file_name="kids_checkin_qr.png", mime="image/png")
