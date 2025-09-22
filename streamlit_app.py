# streamlit_app.py
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
# Secrets & GSpread 연결 유틸
# ------------------------------
def _find_service_account_dict():
    """
    Streamlit Cloud의 secrets.toml에 어떤 키로 서비스 계정이 들어가 있든 최대한 유연하게 잡아준다.
    예시:
    [gcp_service_account] ... or [google_service_account] ... or [service_account] ...
    """
    candidate_keys = ["gcp_service_account", "google_service_account", "service_account"]
    for k in candidate_keys:
        if k in st.secrets:
            return st.secrets[k]
    st.stop()  # 필요한 키가 없으면 앱 중단
    return None

def _find_spreadsheet_info():
    """
    스프레드시트 식별자/워크시트명 가져오기.
    예시:
    [gsheet]
    spreadsheet_id = "xxxx"
    worksheet_name = "checkins"
    """
    # 기본값
    spreadsheet_id = None
    worksheet_name = "checkins"

    if "gsheet" in st.secrets:
        gsheet = st.secrets["gsheet"]
        spreadsheet_id = gsheet.get("spreadsheet_id", spreadsheet_id)
        worksheet_name = gsheet.get("worksheet_name", worksheet_name)

    # 루트에 바로 넣은 경우도 허용
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
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_dict, scope)
    gc = gspread.authorize(creds)

    spreadsheet_id, worksheet_name = _find_spreadsheet_info()
    sh = gc.open_by_key(spreadsheet_id)

    # 워크시트가 없으면 생성, 있으면 가져오기
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=20)
        # 헤더 생성
        ws.append_row(["timestamp_kst", "type", "name", "station", "place"])
    return ws

def append_checkin(row):
    ws = get_worksheet()
    ws.append_row(row)

def fetch_all_records_df():
    ws = get_worksheet()
    # 첫 행을 헤더로 인식하는 구조
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    # 타입 보정
    if "timestamp_kst" in df.columns:
        # ISO-like string -> datetime 변환 시도
        def _parse_dt(x):
            try:
                return pd.to_datetime(x)
            except Exception:
                return pd.NaT
        df["timestamp_kst"] = df["timestamp_kst"].apply(_parse_dt)
    return df

# ------------------------------
# 공통 UI 헤더
# ------------------------------
st.set_page_config(page_title="QR 체크인 시스템", page_icon="✅", layout="wide")
st.title("QR 체크인 시스템")
st.caption("아동안전지킴이 & 자율방범대 — 체크인 • 관리자 요약 • QR 생성기")

# ------------------------------
# 사이드바: 페이지 선택
# ------------------------------
page = st.sidebar.radio(
    "페이지 선택",
    ["대원 체크인", "관리자 요약", "QR 생성기"],
    index=0
)

# ------------------------------
# 유틸: 쿼리파라미터 안전하게 가져오기
# ------------------------------
def get_query_params():
    try:
        # Streamlit 1.33+ : st.query_params
        qp = dict(st.query_params)  # returns Mapping[str, str|list]
        # list 값을 단일로 정규화
        norm = {}
        for k, v in qp.items():
            if isinstance(v, list):
                norm[k] = v[0] if v else ""
            else:
                norm[k] = v
        return norm
    except Exception:
        # 구버전 호환
        qp = st.experimental_get_query_params()
        return {k: (v[0] if isinstance(v, list) and v else v) for k, v in qp.items()}

# ------------------------------
# 페이지 1: 대원 체크인
# ------------------------------
if page == "대원 체크인":
    st.subheader("대원 체크인")
    qp = get_query_params()

    with st.form("checkin_form"):
        col1, col2 = st.columns(2)
        with col1:
            _type = st.selectbox(
                "유형",
                ["아동안전지킴이", "자율방범대"],
                index=0 if qp.get("type", "") not in ["자율방범대"] else 1
            )
            name = st.text_input("이름", value=qp.get("name", ""), placeholder="홍길동")
            station = st.text_input("소속(지구대/초소)", value=qp.get("station", ""), placeholder="일원지구대 / 개포4동 자율방범대")
        with col2:
            place = st.text_input("장소/세부위치", value=qp.get("place", ""), placeholder="○○초 통학로, △△공원 입구 등")
            now_kst = datetime.now(SEOUL_TZ)
            st.info(f"기록 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")

        submitted = st.form_submit_button("체크인 기록")
        if submitted:
            # 필수값 간단 검증
            required_ok = all([_type.strip(), name.strip(), station.strip()])
            if not required_ok:
                st.warning("유형/이름/소속은 필수 항목이야.")
                st.stop()
            row = [
                datetime.now(SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                _type.strip(),
                name.strip(),
                station.strip(),
                place.strip(),
            ]
            append_checkin(row)
            st.success(f"체크인 완료: {_type} · {name} · {station}")
            st.toast("기록되었습니다.", icon="✅")

    st.markdown("---")
    st.caption("Tip: QR로 접속하면 유형/이름/소속/장소가 자동으로 채워져 더 빨라져.")

# ------------------------------
# 페이지 2: 관리자 요약
# ------------------------------
elif page == "관리자 요약":
    st.subheader("관리자 요약")
    df = fetch_all_records_df()
    if df.empty:
        st.info("아직 기록이 없어요.")
    else:
        # 필터
        with st.expander("필터 열기", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                _type = st.multiselect("유형", options=sorted(df["type"].dropna().unique()), default=list(sorted(df["type"].dropna().unique())))
            with c2:
                start_d = st.date_input("시작일", value=(df["timestamp_kst"].dropna().min().date() if df["timestamp_kst"].notna().any() else date.today()))
            with c3:
                end_d = st.date_input("종료일", value=(df["timestamp_kst"].dropna().max().date() if df["timestamp_kst"].notna().any() else date.today()))

        # 필터 적용
        fdf = df.copy()
        if _type:
            fdf = fdf[fdf["type"].isin(_type)]
        if fdf["timestamp_kst"].notna().any():
            fdf = fdf[(fdf["timestamp_kst"].dt.date >= start_d) & (fdf["timestamp_kst"].dt.date <= end_d)]

        # 요약
        st.write("### 집계")
        colA, colB, colC = st.columns(3)
        with colA:
            st.metric("총 체크인 수", len(fdf))
        with colB:
            by_type = fdf.groupby("type").size().to_dict()
            st.write("유형별:", by_type)
        with colC:
            by_station = fdf.groupby("station").size().sort_values(ascending=False).head(5)
            st.write("상위 소속(Top5):")
            st.dataframe(by_station.rename("count"))

        st.markdown("### 기록 테이블")
        st.dataframe(fdf.sort_values(by="timestamp_kst", ascending=False), use_container_width=True)

        # 다운로드
        csv = fdf.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSV 다운로드", data=csv, file_name="checkins_filtered.csv", mime="text/csv")

# ------------------------------
# 페이지 3: QR 생성기
# ------------------------------
elif page == "QR 생성기":
    st.subheader("QR 생성기 (체크인 링크)")
    st.caption("해당 링크로 접속하면 폼이 자동 채워져요.")

    # 배포된 앱의 베이스 URL 입력
    base_url = st.text_input(
        "배포된 앱 URL (예: https://streamlit.app/yourname/kids-guard-qr)",
        placeholder="여기에 본인 앱의 공개 URL 입력"
    )
    c1, c2 = st.columns(2)
    with c1:
        _type = st.selectbox("유형", ["아동안전지킴이", "자율방범대"])
        station = st.text_input("소속(지구대/초소)", placeholder="일원지구대 / 개포4동 자율방범대")
    with c2:
        name = st.text_input("이름", placeholder="홍길동")
        place = st.text_input("장소/세부위치", placeholder="○○초 통학로, △△공원 입구 등")

    if st.button("QR 생성"):
        if not base_url.strip():
            st.warning("배포된 앱의 URL을 입력해줘.")
            st.stop()

        # base_url에 page 파라미터로 '대원 체크인'을 강제하고, 나머지 프리필 파라미터 부여
        params = {
            "page": "대원 체크인",
            "type": _type,
            "name": name,
            "station": station,
            "place": place,
        }

        # 기존 쿼리 유지 + 병합
        parsed = urlparse(base_url)
        existing_q = dict(parse_qsl(parsed.query))
        existing_q.update(params)
        new_q = urlencode(existing_q, doseq=False, encoding="utf-8")
        link = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))

        st.code(link, language="text")

        # QR 이미지 생성
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption="체크인 링크 QR", use_column_width=False)

        st.download_button(
            "QR 이미지 다운로드",
            data=buf.getvalue(),
            file_name=f"checkin_qr_{_type}.png",
            mime="image/png"
        )

    st.markdown("---")
    st.caption("링크에 포함된 파라미터: page, type, name, station, place")

