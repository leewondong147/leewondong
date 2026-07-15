import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.2)")

# 🚨 [사용자 설정] 엑셀 열 번호 (0부터 시작)
st.sidebar.header("엑셀 열 순서 설정 (0부터 시작)")
c_date_idx = st.sidebar.number_input("날짜 열 번호", value=1)
c_name_idx = st.sidebar.number_input("상호 열 번호", value=2)
c_supply_idx = st.sidebar.number_input("공급가액 열 번호", value=3)
c_tax_idx = st.sidebar.number_input("세액 열 번호", value=4)

ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", 0, 100, 50)
kt_threshold = st.sidebar.number_input("KT 소액 기준", value=55000)
kt_new_supply = st.sidebar.number_input("KT 변경 금액", value=0)

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # 데이터 읽기
        df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
        
        # 0: 날짜, 1: 상호 등 설정한 인덱스로 데이터 재구성
        df['작성일자'] = df.iloc[:, c_date_idx]
        df['상호'] = df.iloc[:, c_name_idx]
        df['공급가액'] = pd.to_numeric(df.iloc[:, c_supply_idx].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        df['세액'] = pd.to_numeric(df.iloc[:, c_tax_idx].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        df['합계'] = df['공급가액'] + df['세액']
        
        ansan_list, incheon_list = [], []
        
        for idx, row in df.iterrows():
            name = str(row['상호'])
            date = str(row['작성일자'])
            supply = row['공급가액']
            
            # 분배 로직
            is_split = False
            if any(k in name for k in ['진솔법무사', '비즈택스']): is_split = True
            elif '혜성환경' in name and '0511' in date: is_split = True
            elif ('케이티' in name or 'KT' in name) and supply < kt_threshold:
                if kt_new_supply > 0:
                    row['공급가액'] = float(kt_new_supply)
                    row['세액'] = float(kt_new_supply) * 0.1
                    row['합계'] = row['공급가액'] + row['세액']
                is_split = True
            
            if is_split:
                r_a, r_i = row.copy(), row.copy()
                ratio = ansan_ratio / 100
                r_a['공급가액'] = np.floor(row['공급가액'] * ratio)
                r_a['세액'] = np.floor(row['세액'] * ratio)
                r_a['합계'] = r_a['공급가액'] + r_a['세액']
                r_i['공급가액'] = row['공급가액'] - r_a['공급가액']
                r_i['세액'] = row['세액'] - r_a['세액']
                r_i['합계'] = r_i['공급가액'] + r_i['세액']
                ansan_list.append(r_a); incheon_list.append(r_i)
            else:
                if '남상민' in name or '성남' in name: ansan_list.append(row)
                else: incheon_list.append(row)
        
        a_df, i_df = pd.DataFrame(ansan_list), pd.DataFrame(incheon_list)
        st.dataframe(a_df); st.dataframe(i_df)
    except Exception as e:
        st.error(f"오류: {e}")
