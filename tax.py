import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 환경 설정 (Ver 10.1 최종 통합 정산기)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.1)")
st.caption("비율 슬라이더와 KT 요금 입력 기능이 통합된 최종 완성본입니다.")

# [사이드바] 상세 설정
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.sidebar.divider()

# 비율 설정
st.sidebar.subheader("⚖️ 거래처 분배 비율 설정")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", 0, 100, 50)
incheon_ratio = 100 - ansan_ratio
st.sidebar.caption(f"👉 설정: 안산 {ansan_ratio}% / 인천 {incheon_ratio}%")

st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 (소액 시 변경)")
kt_threshold = st.sidebar.number_input("소액 기준 금액 (공급가액)", value=55000)
kt_new_supply = st.sidebar.number_input("변경할 공급가액 (0: 원본 유지)", value=0)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 2. 정밀 전처리 도구
# ==========================================
def clean_value_secure(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try: return float(val_str)
    except: return 0.0

def parse_flexible_date(series):
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    cleaned = cleaned.str.replace('년', '-').str.replace('월', '-').str.replace('일', '')
    return pd.to_datetime(cleaned, errors='coerce')

if uploaded_file is not None:
    try:
        # 데이터 로드
        df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
        df.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df.columns]

        # 컬럼 매핑
        c_date = next((c for c in df.columns if '일자' in c), df.columns[1])
        c_name = next((c for c in df.columns if any(k in c for k in ['상호', '거래처', '가맹점'])), df.columns[3])
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1])

        # 정제
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        df[c_tax] = df[c_tax].apply(clean_value_secure)
        df['합계'] = df[c_supply] + df[c_tax]
        
        # 분류 및 분배
        ansan_list, incheon_list = [], []
        for idx, row in df.iterrows():
            name_str = str(row[c_name])
            
            # KT 분배 로직
            if ('케이티' in name_str or 'KT' in name_str) and row[c_supply] < kt_threshold:
                if kt_new_supply > 0:
                    row[c_supply] = float(kt_new_supply)
                    row[c_tax] = float(kt_new_supply) * 0.1
                    row['합계'] = row[c_supply] + row[c_tax]
                is_split = True
            # 기타 분배 대상
            elif any(k in name_str for k in ['진솔법무사', '비즈택스']) or ('혜성환경' in name_str and '0511' in str(row[c_date])):
                is_split = True
            else:
                is_split = False

            if is_split:
                r1, r2 = row.copy(), row.copy()
                ratio = ansan_ratio / 100.0
                r1[c_supply] = np.floor(row[c_supply] * ratio)
                r1[c_tax] = np.floor(row[c_tax] * ratio)
                r1['합계'] = r1[c_supply] + r1[c_tax]
                r2[c_supply] = row[c_supply] - r1[c_supply]
                r2[c_tax] = row[c_tax] - r1[c_tax]
                r2['합계'] = r2[c_supply] + r2[c_tax]
                if ansan_ratio > 0: ansan_list.append(r1)
                if incheon_ratio > 0: incheon_list.append(r2)
            else:
                if '남상민' in name_str or any(k in name_str for k in ['성남수정','성남경찰서']): ansan_list.append(row)
                else: incheon_list.append(row)

        # 결과 출력 및 다운로드
        def format_df(lst):
            if not lst: return pd.DataFrame()
            res = pd.DataFrame(lst)
            res = res[[c_date, c_name, c_supply, c_tax, '합계']]
            res.columns = ['작성일자', '상호', '공급가액', '세액', '합계']
            return res

        a_df, i_df = format_df(ansan_list), format_df(incheon_list)
        
        st.success("✅ 정산 완료!")
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점"); st.dataframe(a_df)
        with c2: st.subheader("🏭 인천 지점"); st.dataframe(i_df)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 데이터를 확인해주세요.")
