import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 8.9)")

# 작업 선택
job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (글자 형식으로 안전하게)
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        # 2. 제목 줄(Header) 찾기 로직 강화
        header_row = 0
        found_header = False
        for i in range(min(len(df_raw), 20)): # 상위 20줄 이내에서 탐색
            row_vals = df_raw.iloc[i].fillna('').values
            row_str = "".join(map(str, row_vals))
            # 카드 내역은 '작성일자' 대신 '이용일자' 혹은 '거래일자'일 수 있음
            if any(k in row_str for k in ['일자', '공급가액', '승인번호']):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 🔍 기둥 매칭 (카드 양식에 맞춰 유연하게 선택)
        # 일자 기둥
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['일자', '일시'])), df.columns[0])
        # 상호명 기둥 (가맹점명 등)
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '가맹점', '거래처'])), None)
        if not c_name:
            # 카드 양식에서 상호명이 보통 앞에 위치하므로 안전하게 선택
            c_name = df.columns[3] if len(df.columns) > 3 else df.columns[1]
            
        # 금액 기둥 (공급가액, 세액)
        c_supply = next((c for c in df.columns if '공급가액' in str(c)), None)
        if not c_supply: # 카드 내역에 공급가액 기둥이 따로 없을 경우 '이용금액'이나 '합계'를 찾음
            c_supply = next((c for c in df.columns if any(k in str(c) for k in ['금액', '합계', '승인금액'])), df.columns[-1])
            
        c_tax = next((c for c in df.columns if '세액' in str(c)), None)
        # 세액 기둥이 없으면 0으로 처리하도록 로직 구성

        # 데이터 전처리 및 숫자 변환
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        if c_tax:
            df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        else:
            # 세액 기둥이 없는 경우 공급가액에서 10% 역산 (필요시)
            df['임시세액'] = df[c_supply] * 0.1 / 1.1 # 부가세 포함 금액일 경우 예시
            c_tax = '임시세액'

        df['합계'] = df[c_supply] + df[c_tax]
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 4. 분류 로직
        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            name_val = str(row[c_name]).replace(" ", "").lower()
            
            # [조건 1] 남상민 건 (줄 전체 검색)
            if '남상민' in full_text:
                ansan_list.append(row)
            # [조건 2] 성남/수정/경찰서 (안산)
            elif any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append(row)
            # [조건 3] 카드 내역은 보통 공동비용 분배보다는 명확한 사용처 위주이므로 그대로 분류
            else:
                incheon_list.append(row)

        # 5. 결과 정리 함수
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

        ansan_final = format_df(ansan_list)
        incheon_final = format_df(incheon_list)

        # 6. 다운로드 및 표시
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 카드정산 엑셀 다운로드", output.getvalue(), "호진환경_카드정산_완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점 (카드)"); st.dataframe(ansan_final)
        with c2: st.subheader("🏭 인천 지점 (카드)"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 파일 형식이 평소와 다른지 확인해주세요.")
