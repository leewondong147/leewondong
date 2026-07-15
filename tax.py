import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.7 강화형)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.7 강화형)")

st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", 0, 100, 50)
incheon_ratio = 100 - ansan_ratio

st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 설정")
kt_threshold = st.sidebar.number_input("소액 기준 (공급가액)", value=55000)
kt_new_supply = st.sidebar.number_input("강제 입력 공급가액 (0: 원본 유지)", value=0)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

def clean_value_secure(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try: return float(val_str)
    except: return 0.0

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
        df.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df.columns]

        # 컬럼 매핑 (9.7버전 로직 유지)
        c_date = next((c for c in df.columns if '일자' in c), df.columns[1])
        
        # 매출 시 호진환경 제외 상호 찾기 로직
        if job_type == "💰 매출":
            # 상호가 '호진환경'이 아닌 것을 찾거나, 공급받는자 상호 우선 탐색
            c_name = next((c for c in df.columns if ('상호' in c or '거래처' in c) and '호진' not in str(c)), df.columns[3])
        else:
            c_name = next((c for c in df.columns if '상호' in c or '거래처' in c), df.columns[3])
            
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1])

        df[c_supply] = df[c_supply].apply(clean_value_secure)
        df[c_tax] = df[c_tax].apply(clean_value_secure)

        ansan_list, incheon_list = [], []

        for idx, row in df.iterrows():
            name = str(row[c_name])
            
            # KT 숫자 강제 입력 로직
            if ('케이티' in name or 'KT' in name) and row[c_supply] < kt_threshold:
                if kt_new_supply > 0:
                    row[c_supply] = float(kt_new_supply)
                    row[c_tax] = float(kt_new_supply) * 0.1
            
            # 분배 대상 확인
            is_split = any(k in name for k in ['진솔법무사', '비즈택스', '혜성환경', '케이티', 'KT'])
            
            if is_split:
                ratio = ansan_ratio / 100
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply] = np.floor(row[c_supply] * ratio)
                r_a[c_tax] = np.floor(row[c_tax] * ratio)
                r_i[c_supply] = row[c_supply] - r_a[c_supply]
                r_i[c_tax] = row[c_tax] - r_a[c_tax]
                if ansan_ratio > 0: ansan_list.append(r_a)
                if incheon_ratio > 0: incheon_list.append(r_i)
            else:
                if '남상민' in name or '성남' in name: ansan_list.append(row)
                else: incheon_list.append(row)

        st.success("✅ 정산 완료!")
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점"); st.dataframe(pd.DataFrame(ansan_list)[[c_date, c_name, c_supply, c_tax]])
        with c2: st.subheader("🏭 인천 지점"); st.dataframe(pd.DataFrame(incheon_list)[[c_date, c_name, c_supply, c_tax]])

    except Exception as e:
        st.error(f"🚨 오류: {e}")
