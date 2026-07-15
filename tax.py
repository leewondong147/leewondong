import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.8 수치 입력식 완결판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.8)")
st.caption("비율 슬라이더 대신 실제 사용량을 숫자로 직접 입력하여 정산 분배비를 결정합니다.")

# ==========================================
# ⚙️ [사이드바] 사용량 직접 입력 제어판
# ==========================================
st.sidebar.header("⚙️ 수치 기반 정산 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("🔢 사용량 직접 입력 (분배용)")
ansan_usage = st.sidebar.number_input("안산 본점 사용량 (단위: 수치)", value=50, step=1)
incheon_usage = st.sidebar.number_input("인천 지점 사용량 (단위: 수치)", value=50, step=1)

# 합계 사용량 계산
total_usage = ansan_usage + incheon_usage
ansan_ratio = (ansan_usage / total_usage) if total_usage > 0 else 0.5
incheon_ratio = (incheon_usage / total_usage) if total_usage > 0 else 0.5

st.sidebar.caption(f"👉 실시간 분배 비율: 안산 {ansan_ratio*100:.1f}% / 인천 {incheon_ratio*100:.1f}%")

st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 설정")
kt_threshold = st.sidebar.number_input("소액 기준 (공급가액 기준)", value=55000, step=1000)
kt_new_supply = st.sidebar.number_input("소액 시 변경할 공급가액 (0: 원본)", value=0, step=1000)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# [중략: 기존의 clean_value_secure, parse_flexible_date 및 파일 로드/매핑 로직은 동일]
# 아래는 동일한 구조이므로 생략 없이 바로 핵심 연산부만 적용합니다.

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
        if uploaded_file.name.endswith('.csv'): df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else: df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        header_row = 0
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(map(str, df_raw.iloc[i].fillna('').values))
            cleaned_row = re.sub(r'[^가-힣a-zA-Z0-9]', '', row_str)
            if any(k in cleaned_row for k in ['일자', '공급가액', '승인번호', '상호', '세액']):
                header_row = i
                break
        
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, skiprows=header_row) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=header_row)
        df.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df.columns]

        c_date = next((c for c in df.columns if '작성일자' in c or '일자' in c), df.columns[1])
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '가맹점', '거래처']) and str(c) != c_date), df.columns[3])
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), '임시세액')

        df[c_supply] = df[c_supply].apply(clean_value_secure)
        if c_tax == '임시세액': df['임시세액'] = df[c_supply] * 0.1; c_tax = '임시세액'
        else: df[c_tax] = df[c_tax].apply(clean_value_secure)
        df['합계'] = df[c_supply] + df[c_tax]
        
        parsed_dates = parse_flexible_date(df[c_date])
        df['월'] = parsed_dates.dt.month.fillna(0).astype(int)
        df['일'] = parsed_dates.dt.day.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            name_str = str(row[c_name]).replace(" ", "").lower()
            
            is_split_target = False
            if '진솔법무사' in name_str or '비즈택스' in name_str or ('혜성환경' in name_str and row['월'] == 5 and row['일'] == 11):
                is_split_target = True
            elif '케이티' in name_str or 'kt' in name_str:
                if row[c_supply] < kt_threshold:
                    if kt_new_supply > 0: row[c_supply], row[c_tax] = float(kt_new_supply), float(kt_new_supply)*0.1
                    row['합계'] = row[c_supply] + row[c_tax]
                    is_split_target = True

            if is_split_target:
                row_ansan, row_incheon = row.copy(), row.copy()
                row_ansan[c_supply] = np.floor(row[c_supply] * ansan_ratio)
                row_ansan[c_tax] = np.floor(row[c_tax] * ansan_ratio)
                row_ansan['합계'] = row_ansan[c_supply] + row_ansan[c_tax]
                row_incheon[c_supply] = row[c_supply] - row_ansan[c_supply]
                row_incheon[c_tax] = row[c_tax] - row_ansan[c_tax]
                row_incheon['합계'] = row_incheon[c_supply] + row_incheon[c_tax]
                if ansan_ratio > 0: ansan_list.append(row_ansan)
                if incheon_ratio > 0: incheon_list.append(row_incheon)
                continue
            
            if '남상민' in full_text or any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']): ansan_list.append(row)
            else: incheon_list.append(row)

        def format_df(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_df = temp[[c_date, c_name, c_supply, c_tax, '합계']].copy()
            display_df.columns = ['작성일자', '상호', '공급가액', '세액', '합계']
            
            final_rows = []
            display_df['temp_month'] = parse_flexible_date(display_df['작성일자']).dt.month.fillna(0).astype(int)
            for m, g in display_df.groupby('temp_month'):
                final_rows.append(g.drop(columns=['temp_month']))
                final_rows.append(pd.DataFrame([{'작성일자': f"{int(m)}월 소계", '상호': "", '공급가액': g['공급가액'].sum(), '세액': g['세액'].sum(), '합계': g['합계'].sum()}]))
            final_rows.append(pd.DataFrame([{'작성일자': "총 계", '상호': "", '공급가액': display_df['공급가액'].sum(), '세액': display_df['세액'].sum(), '합계': display_df['합계'].sum()}]))
            return pd.concat(final_rows, ignore_index=True)

        ansan_final, incheon_final = format_df(ansan_list), format_df(incheon_list)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료.xlsx")
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)
    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
