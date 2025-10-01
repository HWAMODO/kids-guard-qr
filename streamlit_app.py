# streamlit_app.py — 아동안전지킴이 전용 (수서경찰서 관내 초등학교 26개)
import streamlit as st
from datetime import datetime
import pytz
import pandas as pd

# gspread + oauth2client (Cloud secrets의 \\n → \n 변환)
from oauth2client.service_account import ServiceAccountCredentials
import gspread

APP_VERSION = "seq-4cols-2025-10-02"  # 버전 확인용(사이드바에 표시)
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
# GSpread 연결 + 헤더 강제 + 연번 자동
# ------------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
EXPECTED_HEADER = ["연번", "이름", "근무장소", "근무시간"]  # 최종 요구 포맷

@st.cache_resource(show_spinner=False)
def get_worksheet():
    # 1) 시크릿 읽기 + private_key 개행 복원
    sa_dict = dict(st.secrets["gcp_service_account"])
    sa_dict["private_key"] = sa_dict["private_key"].replace("\\n", "\n")

    # 2) 인증/클라이언트
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_dict, SCOPE)
    client = gspread.authorize(creds)

    # 3) 스프레드시트/워크시트 열기
    #    필요 시 open_by_key로 바꾸려면: sh = client.open_by_key(st.secrets["gspread"]["sheet_id"])
    sh = client.open("체크인기록")
    try:
        ws = sh.worksheet("Sheet1")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Sheet1", rows=1000, cols=20)

    # 4) 헤더 강제(1행)
    header = ws.row_values(1)
    if header[:4] != EXPECTED_HEADER:
        ws.update("A1:D1", [EXPECTED_HEADER])
    return ws

def append_checkin_ordered(name: str, school: str, ts_kst: str):
    """
    시트에 [연번, 이름, 근무장소, 근무시간] 순서로 기록.
    연번 = 현재 A열(연번) 값 개수  (헤더 포함이므로 다음 인덱스)
    """
    ws = get_worksheet()
    # 헤더 보장
    header = ws.row_values(1)
    if header[:4] != EXPECTED_HEADER:
        ws.update("A1:D1", [EXPECTED_HEADER])

    # 현재 연번 계산 (A열 값 개수)
    colA = ws.col_values(1)      # 예: ["연번","1","2",...]
    next_seq = len(colA)         # 헤더 포함 길이 = 다음 연번

    row = [next_seq, name.strip(), school, ts_kst]
    ws.append_row(row)

def fetch_all_records_df():
    ws = get_worksheet()
    records = ws.get_all_records()  # 1행을 헤더로 인식
    df = pd.DataFrame(records)

    # 새/구 헤더 모두 대응 (과거 잘못 들어간 행 섞여있을 경우 대비)
    rename_map = {
        "근무시간": "timestamp_kst",
        "이름": "name",
        "근무장소": "school",
        "연번": "seq",
        # 과거 포맷(예: timestamp_kst/type/name/school) 대응
        "timestamp_kst": "timestamp_kst",
        "name": "name",
        "school": "school",
        "seq": "seq",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "timestamp_kst" in df.columns:
        df["timestamp_kst"] = pd.to_datetime(df["timestamp_kst"], errors="coerce")
    return df

# ------------------------------
# 기본 UI
# ------------------------------
st.set_page_config(page_title="아동안전지킴이 QR 체크인", page_icon="✅", layout="wide")
st.title("아동안전지킴이 QR 체크인")
st.caption("수서경찰서 관내 초등학교 전용 시스템")
st.sidebar.info(f"VERSION: {APP_VERSION}")

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
            # 특이사항은 UI에만 표시(요청 포맷 유지: 시트에는 저장하지 않음)
            note = st.text_area(
                "특이사항(시트 미저장)", value=qp.get("note", ""),
                placeholder="예) 통학로 상황 양호, 주변 공원 인원 증가 등", height=88
            )
            now_kst = datetime.now(SEOUL_TZ)
            st.info(f"기록 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
        submitted = st.form_submit_button("체크인 기록")

        if submitted:
            if not name.strip():
                st.warning("이름은 필수 입력입니다.")
                st.stop()
            ts_kst = datetime.now(SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S")
            try:
                # ★ [연번, 이름, 근무장소, 근무시간] 순서로만 저장
                append_checkin_ordered(name=name.strip(), school=school, ts_kst=ts_kst)
                # ★ 성공 문구에서 '아동안전지킴이' 제거
                st.success(f"체크인 완료: {name} · {school}")
                st.toast("기록되었습니다.", icon="✅")
            except Exception as e:
                st.error("기록 중 오류가 발생했습니다. (관리자 확인 필요)")
                # 필요 시 디버그:
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
        # 시간 컬럼 잡기
        time_col = "timestamp_kst" if "timestamp_kst" in df.columns else (
            "근무시간" if "근무시간" in df.columns else None
        )
        if time_col and df[time_col].dtype == "O":
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

        with st.expander("필터", expanded=True):
            c1, c2 = st.columns(2)
            if time_col:
                with c1:
                    start_d = st.date_input("시작일", value=pd.to_datetime(df[time_col]).min().date())
                with c2:
                    end_d = st.date_input("종료일", value=pd.to_datetime(df[time_col]).max().date())
            else:
                start_d = st.date_input("시작일")
                end_d = st.date_input("종료일")

        if time_col:
            fdf = df[(pd.to_datetime(df[time_col]).dt.date >= start_d) &
                     (pd.to_datetime(df[time_col]).dt.date <= end_d)]
        else:
            fdf = df.copy()

        # 보기 좋게 컬럼 순서 통일
        for old, new in [("연번","seq"),("이름","name"),("근무장소","school"),("근무시간","timestamp_kst")]:
            if old in fdf.columns and new not in fdf.columns:
                fdf = fdf.rename(columns={old:new})

        show_cols = ["seq","name","school","timestamp_kst"]
        ordered = [c for c in show_cols if c in fdf.columns]
        sort_key = ordered[-1] if ordered else (fdf.columns[0] if len(fdf.columns) else None)

        st.metric("총 체크인 수", len(fdf))
        if sort_key:
            st.dataframe(fdf.sort_values(sort_key, ascending=False), use_container_width=True)
        else:
            st.dataframe(fdf, use_container_width=True)

        csv = fdf.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSV 다운로드", data=csv, file_name="checkins_kids.csv", mime="text/csv")
