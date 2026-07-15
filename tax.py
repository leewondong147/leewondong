import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.4)")

# [사이드바] 열 번호 수동 설정
st.sidebar.header("⚙️ 엑셀 열 번호 설정 (필수)")
job_type = st.sidebar.radio("작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
c_date_idx = st.sidebar.number_input("날짜 열 번호 (A=0, B=1...)", value=1)
c_name_idx = st.sidebar.number_input("상호 열 번호", value=2)
c_supply_idx = st.sidebar.number_input("공급가액 열 번호", value=3)
c_tax_idx = st.sidebar.number_input("세액 열 번호", value=4)

st.sidebar.divider()
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", 0, 100, 50)
kt_threshold = st.sidebar.number_input("KT 소액 기준 (공급가액)", value=55000)
kt_new_supply = st.sidebar.number_input("KT 변경 금액 (0: 원본)", value=0)

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # 1. 파일 읽기
        df = pd.read_excel(uploaded_file, header=None) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None)
        
        # 2. 🚨 가장 중요한 부분: 무조건 지정한 열 번호로 데이터 추출 후 이름 고정
        df_clean = pd.DataFrame()
        df_clean['작성일자'] = df.iloc[:, c_date_idx].astype(str)
        df_clean['상호'] = df.iloc[:, c_name_idx].astype(str)
        df_clean['공급가액'] = pd.to_numeric(df.iloc[:, c_supply_idx].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        df_clean['세액'] = pd.to_numeric(df.iloc[:, c_tax_idx].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        df_clean['합계'] = df_clean['공급가액'] + df_clean['세액']
        
        ansan_list, incheon_list = [], []
        
        # 3. 정산 및 분류
        for idx, row in df_clean.iterrows():
            name = str(row['상호'])
            supply = row['공급가액']
            
            # KT 및 기타 분배 로직
            is_split = False
            if ('진솔법무사' in name or '비즈택스' in name or '혜성환경' in name or '케이티' in name or 'KT' in name):
                if ('케이티' in name or 'KT' in name) and supply >= kt_threshold:
                    is_split = False
                else:
                    if ('케이티' in name or 'KT' in name) and kt_new_supply > 0:
                        row['공급가액'] = float(kt_new_supply)
                        row['세액'] = float(kt_new_supply) * 0.1
                        row['합계'] = row['공급가액'] + row['세액']
                    is_split = True
            
            if is_split:
                ratio = ansan_ratio / 100
                r_a, r_i = row.copy(), row.copy()
                r_a['공급가액'] = np.floor(row['공급가액'] * ratio)
                r_a['세액'] = np.floor(row['세액'] * ratio)
                r_a['합계'] = r_a['공급가액'] + r_a['세액']
                r_i['공급가액'] = row['공급가액'] - r_a['공급가액']
                r_i['세액'] = row['세액'] - r_a['세액']
                r_i['합계'] = r_i['공급가액'] + r_i['세액']
                if ansan_ratio > 0: ansan_list.append(r_a)
                if (100-ansan_ratio) > 0: incheon_list.append(r_i)
            else:
                if '남상민' in name or '성남' in name: ansan_list.append(row)
                else: incheon_list.append(row)
        
        st.success("✅ 정산 완료!")
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산"); st.dataframe(pd.DataFrame(ansan_list))
        with c2: st.subheader("🏭 인천"); st.dataframe(pd.DataFrame(incheon_list))
        
    except Exception as e:
        st.error(f"🚨 오류: {e} - 사이드바의 열 번호가 엑셀과 맞는지 확인해주세요!")
