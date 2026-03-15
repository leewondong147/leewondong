import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 6.3)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        # 2. 제목 줄 찾기
        skip_idx = 0
        for i in range(len(df_raw)):
            line = "".join([str(v) for v in df_raw.iloc[i].values])
            if any(k in line for k in ['공급', '세액', '금액', '상호', '일자']):
                skip_idx = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=skip_idx)
        else:
            df = pd.read_excel(uploaded_file, skiprows=skip_idx)

        # 3. 기둥 이름 매칭 및 일자 처리
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['일자', '날짜', '작성일'])), df.columns[0])
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자', '거래처', '고객'])), df.columns[1])
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        if not c_supply: c_supply = next((c for c in df.columns if '금액' in str(c) or '공급' in str(c)), df.columns[2])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)
        if not c_tax: c_tax = next((c for c in df.columns if '세' in str(c)), df.columns[3])

        # 숫자 및 날짜 정리
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 4. 분류 작업 (공동 비용을 '가장 먼저' 검사)
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            supply_val = float(row[c_supply])
            tax_val = float(row[c_tax])

            # [A] 공동 비용 (최우선 순위)
            # 1. 비즈텍스/기장료
            if any(k in name_val for k in ['비즈', '택스', 'tax', '세무']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            
            # 2. KT/전화요금 (질문창 띄우기)
            elif any(k in name_val for k in ['kt', '케이티', '전화', '통신']):
                st.info(f"💡 공동요금 발견: {row[c_name]} ({supply_val:,.0f}원)")
                ansan_v = st.number_input(f"ㄴ {row[c_name]} 중 안산분 금액?", 0.0, float(supply_val), float(supply_val/2), key=f"q_{idx}")
                
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                ansan_list.append(r_a)
                incheon_list.append(r_i)

            # [B] 일반 분류
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 5. 합계 및 소계 계산 함수
        def add_summary(data_list):
            if not data_list: return pd.DataFrame()
            res_df = pd.DataFrame(data_list)
            # 월별 소계
            monthly_sum = res_df.groupby('월')[[c_supply, c_tax]].sum().reset_index()
            monthly_sum[c_name] = monthly_sum['월'].apply(lambda x: f"--- {x}월 소계 ---")
            
            # 전체 합계
            total_supply = res_df[c_supply].sum()
            total_tax = res_df[c_tax].sum()
            total_row = pd.DataFrame([{c_name: "=== 총 합계 ===", c_supply: total_supply, c_tax: total_tax}])
            
            return pd.concat([res_df, monthly_sum, total_row], ignore_index=True)

        ansan_final = add_summary(ansan_list)
        incheon_final = add_summary(incheon_list)

        # 6. 결과 출력
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏢 안산 (본점)")
            st.dataframe(ansan_final)
            if not ansan_final.empty:
                st.download_button("📥 안산 엑셀 다운로드", ansan_final.to_csv(index=False).encode('utf-8-sig'), "ansan_with_total.csv")
        with col2:
            st.subheader(f"🏭 인천 (지점)")
            st.dataframe(incheon_final)
            if not incheon_final.empty:
                st.download_button("📥 인천 엑셀 다운로드", incheon_final.to_csv(index=False).encode('utf-8-sig'), "incheon_with_total.csv")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
