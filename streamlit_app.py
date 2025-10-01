# streamlit_app.py — 아동안전지킴이 전용 (수서경찰서 관내 초등학교 26개)
import streamlit as st
from datetime import datetime
import pytz
import pandas as pd

# gspread + oauth2client (Cloud secrets의 \\n → \n 변환)
from oauth2client.service_account import ServiceAccountCredentials
import gspread

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
# GSpread 연결 (secrets의 \\n → \n 변환 포함)
# ------------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource(show_spinner=False)
def get_worksheet():
    # 1) 시크릿 읽기
    if "gcp_service_account" not in st.secrets:
        st.stop()  # Cloud에 secrets 미설정시 중단
    sa_dict = dict(st.secrets["gcp_service_account"])

    # 2) ★ 핵심: private_key의 \\n 을 실제 개행으로 변환
    if "private_key" in sa_dict and "\\n" in sa_dict["private_key"]:
        sa_dict["private_key"] = sa_dict["private_key"].replace("\\n", "\n")

    # 3) 인증 및 클라이언트 생성
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_dict, SCOPE)
    client = gspread.authorize(creds)

    # 4) 스프레드시트 열기 (이름/시트명은 현장 기준)
    sh = client.open("체크인기록")
    try:
        ws = sh.worksheet("Sheet1")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Sheet1", rows=1000, cols=20)
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
# 쿼리파라미터 (name/school/note 프리필)
# ------------------------------
def get_query_params():
    try:
        qp = dict(st.query_params)
        return {k: (v[0] if isinstance(v, list) else v) for k, v in qp.items()}
    except Exception:
        qp = st.experimental_get_query_params()
        return {k: (v[0] if isinstance(v, list) else v) for k, v in qp.items()}

PAGES = ["대원 체크인", "관리자 요약"]  # QR 생성기 제거
qp = get_query_params()
default_index = PAGES.index(qp["page"]) if "page" in qp and qp["page"] in PAGES else 0
page = st.sidebar.radio("페이지 선택", PAGES, index=default_index)

# ------------------------------
# 페이지 1: 대원 체크인
# ------------------------------
if page == "대원 체크인":
    st.subheader("대원 체크인")
    with st.form("checkin_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("이름", value=qp.get("name", ""), placeholder="홍길동")
            school = st.selectbox(
                "학교",
                SCHOOL_OPTIONS,
                index=SCHOOL_OPTIONS.index(qp["school"]) if qp.get("school") in SCHOOL_OPTIONS else 0
            )
        with col2:
            note = st.text_area(
                "특이사항", value=qp.get("note", ""),
                placeholder="예) 통학로 상황 양호, 주변 공원 인원 증가 등", height=88
            )
            now_kst = datetime.now(SEOUL_TZ)
            st.info(f"기록 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
        submitted = st.form_submit_button("체크인 기록")

        if submitted:
            if not name.strip():
                st.warning("이름은 필수 입력입니다.")
                st.stop()
            row = [
                datetime.now(SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                "아동안전지킴이",
                name.strip(),
                school,
                note.strip()
            ]
            try:
                append_checkin(row)
                st.success(f"체크인 완료: 아동안전지킴이 · {name} · {school}")
                st.toast("기록되었습니다.", icon="✅")
            except Exception as e:
                st.error("기록 중 오류가 발생했습니다. (관리자 확인 필요)")
                # 디버그용: 필요 시 주석 해제
                # st.exception(e)

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
            c1, c2 = st.columns(2)
            with c1:
                start_d = st.date_input("시작일", value=df["timestamp_kst"].min().date())
            with c2:
                end_d = st.date_input("종료일", value=df["timestamp_kst"].max().date())
        fdf = df[(df["timestamp_kst"].dt.date >= start_d) & (df["timestamp_kst"].dt.date <= end_d)]
        st.metric("총 체크인 수", len(fdf))
        st.dataframe(fdf.sort_values("timestamp_kst", ascending=False), use_container_width=True)
        csv = fdf.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSV 다운로드", data=csv, file_name="checkins_kids.csv", mime="text/csv")
