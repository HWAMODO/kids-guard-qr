import streamlit as st
from log_to_sheet import log_checkin

st.set_page_config(page_title="체크인 폼")

st.title("✅ 아동안전지킴이 체크인 폼")

# 📌 URL 쿼리 파라미터로 학교명 받기
school_from_url = st.query_params.get("school", "")


# ✏️ 이름은 입력
name = st.text_input("👮‍♀️ 이름을 입력하세요:")

# 🏫 학교는 URL에서 왔으면 수정 불가 / 없으면 직접 입력
if school_from_url:
    st.text_input("🏫 초등학교 이름", value=school_from_url, disabled=True)
    school = school_from_url
else:
    school = st.text_input("🏫 초등학교 이름을 입력하세요:")

# ✅ 체크인 버튼
if st.button("📌 체크인"):
    if name and school:
        log_checkin(name, school)
        st.success("🎉 체크인이 성공적으로 기록되었습니다!")
    else:
        st.error("⚠️ 이름과 학교를 모두 입력해주세요.")
