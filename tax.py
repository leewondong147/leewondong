import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.3)")

# [사이드바] 열 번호 수동 설정 (에러 방지용)
st.sidebar.header("⚙️ 엑셀 위치 수동 설정 (필수)")
job_type = st.sidebar.radio("작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
c_date_idx = st.sidebar.number_input("날짜 열 번호 (A=0, B=1...)", value=1)
c_name_idx = st.sidebar.number_input("상호 열 번호", value=3) # 매출 시 수신자 상호 위치
c_supply_idx = st.sidebar.number_input("공급가액 열 번호", value=5)
c_tax_idx = st.sidebar.number_input("세액 열 번호", value=6)

st.sidebar.divider()
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", 0, 100, 50)
kt_new_supply = st.sidebar.number_input("KT 변경 공급가액 (0: 원본 유지)", value=0)

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # 데이터 로드
        df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
        
        # 1. 정제 함수
        def clean(x):
            try: return float(str(x).replace(',','').replace('원','').strip())
            except: return 0.0

        # 2. 강제 위치 매핑 (열 이름 대신 열 번호 사용)
        df['작성일자'] = df.iloc[:, c_date_idx]
        df['상호'] = df.iloc[:, c_name_idx]
        df['공급가액'] = df.iloc[:, c_supply_idx].apply(clean)
        df['세액'] = df.iloc[:, c_tax_idx].apply(clean)
        df['합계'] = df['공급가액'] + df['세액']
        
        ansan_list, incheon_list = [], []
        
        # 3. 정산 및 분배
        for idx, row in df.iterrows():
            name = str(row['상호'])
            supply = row['공급가액']
            
            # KT 로직
            if ('케이티' in name or 'KT' in name) and kt_new_supply > 0:
                row['공급가액'] = float(kt_new_supply)
                row['세액'] = float(kt_new_supply) * 0.1
                row['합계'] = row['공급가액'] + row['세액']
            
            # 분배 대상 여부 (진솔, 비즈택스, 혜성, KT)
            is_split = any(k in name for k in ['진솔법무사', '비즈택스', '혜성환경', '케이티', 'KT'])
            
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
        st.dataframe(pd.DataFrame(ansan_list)[['작성일자','상호','공급가액','세액','합계']])
        st.dataframe(pd.DataFrame(incheon_list)[['작성일자','상호','공급가액','세액','합계']])
        
    except Exception as e:
        st.error(f"🚨 오류: {e} - 사이드바의 열 번호가 엑셀과 맞는지 확인해주세요!")
