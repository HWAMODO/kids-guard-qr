# admin_qr_checkin_only.py
# 🎯 목적: 아동안전지킴이 QR 체크인 "기록 관리" 화면만 단독 실행 (Streamlit)
# - 데이터 원천: 구글시트 "체크인기록" / 워크시트 "Sheet1"
# - 컬럼 가정: ["연번", "이름", "근무장소", "근무시간"]  ← 기존 log_to_sheet.py 기준
# - secrets.toml의 [gcp_service_account]를 사용 (하드코딩 금지)

import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io

# -------------------------------
# 기본 페이지 설정
# -------------------------------
st.set_page_config(page_title="아동안전지킴이 QR 체크인 관리자", layout="wide")
st.title("👶 아동안전지킴이 QR 체크인 관리자 대시보드")
st.caption("구글시트에 누적된 체크인 기록을 조회·필터·다운로드")

# -------------------------------
# Google Sheets 연결
# -------------------------------
@st.cache_resource(show_spinner=False)
def _get_gspread_client():
    # Streamlit Cloud/로컬 공통: secrets.toml로부터 보안 키 로드
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "secrets.toml에 [gcp_service_account]가 없습니다. "
            "아래 '⚙️ 운영 팁 / 환경 설정' 섹션을 확인하세요."
        )
    raw = dict(st.secrets["gcp_service_account"])
    # 개행 복원
    if "private_key" in raw:
        raw["private_key"] = raw["private_key"].replace("\\n", "\n")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(raw, scope)
    return gspread.authorize(creds)

def load_sheet(spread_name="체크인기록", worksheet_name="Sheet1") -> pd.DataFrame:
    client = _get_gspread_client()
    sh = client.open(spread_name).worksheet(worksheet_name)
    values = sh.get_all_values()
    if not values:
        return pd.DataFrame(columns=["연번", "이름", "근무장소", "근무시간"])
    header, rows = values[0], values[1:]
    df = pd.DataFrame(rows, columns=[h.strip() for h in header])

    # 예상 컬럼 보강
    needed = ["연번", "이름", "근무장소", "근무시간"]
    for c in needed:
        if c not in df.columns:
            df[c] = ""

    # 시간 파싱 (KST)
    def parse_kst(x):
        x = str(x).strip()
        try:
            dt = pd.to_datetime(x, errors="coerce")
            if pd.isna(dt):
                return pd.NaT
            kst = pytz.timezone("Asia/Seoul")
            if dt.tzinfo is None:
                return kst.localize(dt)
            return dt.astimezone(kst)
        except Exception:
            return pd.NaT

    df["근무시간_dt"] = df["근무시간"].apply(parse_kst)
    df["날짜"] = df["근무시간_dt"].dt.date
    df["시간"] = df["근무시간_dt"].dt.strftime("%H:%M:%S")

    # 연번 숫자 변환
    def to_int(x):
        try:
            return int(str(x).strip())
        except Exception:
            return None
    df["연번"] = df["연번"].apply(to_int)

    return df

# -------------------------------
# 사이드바 필터
# -------------------------------
with st.sidebar:
    st.header("🔎 필터")
    st.subheader("날짜 범위")
    today = datetime.now(pytz.timezone("Asia/Seoul")).date()
    default_start = today - timedelta(days=14)
    start_date = st.date_input("시작일", value=default_start)
    end_date = st.date_input("종료일", value=today)

    st.subheader("조건")
    name_kw = st.text_input("이름(포함 검색)", value="")
    place_kw = st.text_input("근무장소(포함 검색)", value="")
    refresh = st.button("🔄 새로고침")

# 새로고침 버튼
if refresh:
    st.experimental_rerun()

# -------------------------------
# 데이터 로드 & 필터링
# -------------------------------
with st.spinner("구글시트에서 데이터를 가져오는 중..."):
    try:
        df = load_sheet()
    except Exception as e:
        st.error("구글시트 연결 또는 데이터 로드 중 오류가 발생했습니다.")
        st.exception(e)
        st.stop()

total_cnt = len(df)
df_f = df.copy()

# 날짜 필터
if start_date:
    df_f = df_f[df_f["날짜"] >= start_date]
if end_date:
    df_f = df_f[df_f["날짜"] <= end_date]

# 키워드 필터
if name_kw.strip():
    df_f = df_f[df_f["이름"].astype(str).str.contains(name_kw.strip(), na=False)]
if place_kw.strip():
    df_f = df_f[df_f["근무장소"].astype(str).str.contains(place_kw.strip(), na=False)]

# -------------------------------
# 요약 지표
# -------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("총 체크인", f"{total_cnt:,} 건")
col2.metric("조회 결과", f"{len(df_f):,} 건")
col3.metric("인원 수(고유)", f"{df_f['이름'].nunique():,} 명")
col4.metric("근무장소 수(고유)", f"{df_f['근무장소'].nunique():,} 곳")

st.markdown("---")

# -------------------------------
# 일자별 추이(간단 차트)
# -------------------------------
if not df_f.empty:
    daily_counts = df_f.groupby("날짜").size().sort_index()
    st.subheader("📈 일자별 체크인 추이")
    st.line_chart(daily_counts, height=220)
else:
    st.info("선택된 조건에 해당하는 데이터가 없습니다.")

# -------------------------------
# 표 & 다운로드
# -------------------------------
st.subheader("🗂️ 체크인 내역")
show_cols = ["연번", "이름", "근무장소", "근무시간", "날짜", "시간"]
table_df = df_f[show_cols].sort_values(by=["근무시간"], ascending=False)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)

def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    dataframe.to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue().encode("utf-8-sig")

st.download_button(
    label="⬇️ CSV로 내려받기",
    data=to_csv_bytes(table_df),
    file_name=f"kids_guard_checkins_{start_date}_to_{end_date}.csv",
    mime="text/csv"
)

st.info("필드 기준: 연번 / 이름 / 근무장소 / 근무시간(원본) / 날짜 / 시간")

# -------------------------------
# 운영 팁
# -------------------------------
with st.expander("⚙️ 운영 팁 / 환경 설정"):
    st.markdown(
        """
- **secrets.toml**에 `gcp_service_account` 키가 있어야 합니다.  
- 스프레드시트 이름과 시트명은 기본값 **체크인기록 / Sheet1**을 사용합니다.  
- 기록 컬럼은 **[연번, 이름, 근무장소, 근무시간]**을 가정합니다.
        """
    )
