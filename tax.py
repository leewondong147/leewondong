import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 8.5)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        header_row = 0
        for i in range(len(df_raw)):
            row_vals = df_raw.iloc[i].fillna('').values
            row_str = "".join(map(str, row_vals))
            if '작성일자' in row_str and '공급가액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, skiprows=header_row) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=header_row)

        # 1. 기둥 매칭 정밀 보정
        c_date = next((c for c in df.columns if '작성일자' in str(c)), df.columns[0])
        
        # [핵심 수정] 상호명 기둥을 더 엄격하게 찾습니다.
        if "매출" in job_type:
            # 매출: 10번~14번 기둥 사이에서 '상호'가 있고 '주소', '대표', '번호'가 없는 것을 선택
            c_name = None
            for col in df.columns[10:15]:
                if '상호' in str(col) and not any(k in str(col) for k in ['주소', '대표', '번호', '등록']):
                    c_name = col
                    break
            if not c_name: c_name = df.columns[12] # 표준 위치 강제 지정
        else:
            # 매입: 5번~9번 기둥 사이에서 동일 조건 적용
            c_name = None
            for col in df.columns[5:10]:
                if '상호' in str(col) and not any(k in str(col) for k in ['주소', '대표', '번호', '등록']):
                    c_name = col
                    break
            if not c_name: c_name = df.columns[6] # 표준 위치 강제 지정
            
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '품목' not in str(c)), df.columns[15])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '품목' not in str(c)), df.columns[16])

        # 숫자 및 전처리
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df['합계'] = df[c_supply] + df[c_tax]
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 2. 분류 작업
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            
            shared_keywords = ['세무', '비즈', 'tax', '한국전자인증', '전자인증', 'nice평가', '나이스평가']
            
            is_ansan_email = any(k in full_text for k in ['6114hojin', 'tpy1004', 'tpywater'])
            is_ansan_police = any(k in name_val for k in ['성남수정', '성남경찰서']) or any(k in full_text for k in ['성남수정', '성남경찰서'])
            
            if "매입" in job_type and any(k in name_val for k in shared_keywords):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax], r_a['합계'] = row[c_supply]/2, row[c_tax]/2, row['합계']/2
                r_i[c_supply], r_i[c_tax], r_i['합계'] = row[c_supply]/2, row[c_tax]/2, row['합계']/2
                ansan_list.append(r_a); incheon_list.append(r_i)
            elif "매입" in job_type and any(k in name_val for k in ['kt', '케이티', '전화']):
                st.info(f"📞 공동요금: {row[c_name]} (총 {row[c_supply]:,.0f}원)")
                ansan_v = st.number_input(f"ㄴ {row[c_name]} 안산분 공급가액?", 0.0, float(row[c_supply]), float(row[c_supply]/2), key=f"kt_{idx}")
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax], r_a['합계'] = ansan_v, ansan_v*0.1, ansan_v*1.1
                r_i[c_supply], r_i[c_tax], r_i['합계'] = row[c_supply]-ansan_v, (row[c_supply]-ansan_v)*0.1, (row[c_supply]-ansan_v)*1.1
                ansan_list.append(r_a); incheon_list.append(r_i)
            elif (is_ansan_email or is_ansan_police) and ('hojinbio' not in full_text):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 3. 정리 및 엑셀 출력
        def format_df(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_df = pd.DataFrame()
            display_df['작성일자'] = temp[c_date]
            display_df['상호'] = temp[c_name]
            display_df['공급가액'] = temp[c_supply]
            display_df['세액'] = temp[c_tax]
            display_df['합계'] = temp['합계']
            
            final_rows = []
            for month, group in display_df.groupby(display_df['작성일자'].apply(lambda x: pd.to_datetime(x).month if pd.notnull(pd.to_datetime(x, errors='coerce')) else 0)):
                final_rows.append(group)
                sub = pd.DataFrame([{'작성일자': f"{int(month)}월 소계", '상호': "", '공급가액': group['공급가액'].sum(), '세액': group['세액'].sum(), '합계': group['합계'].sum()}])
                final_rows.append(sub)
            
            grand = pd.DataFrame([{'작성일자': "총 계", '상호': "", '공급가액': display_df['공급가액'].sum(), '세액': display_df['세액'].sum(), '합계': display_df['합계'].sum()}])
            final_rows.append(grand)
            return pd.concat(final_rows, ignore_index=True)

        ans
