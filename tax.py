import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 7.5)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        header_row = 0
        for i in range(len(df_raw)):
            row_str = "".join([str(v) for v in df_raw.iloc[i].values])
            if '작성일자' in row_str and '공급가액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, skiprows=header_row) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, skiprows=header_row)

        # 1. 기둥 매칭 - 더 정밀하게 수정
        c_date = next((c for c in df.columns if '작성일자' in str(c)), df.columns[0])
        
        # 상호명 찾기 로직 강화: '대표자'나 '성명'이라는 단어가 들어간 기둥은 제외하고 '상호'만 찾습니다.
        if "매출" in job_type:
            # 매출일 때는 '공급받는자' + '상호'가 둘 다 들어있는 기둥을 찾습니다.
            c_name = next((c for c in df.columns if '상호' in str(c) and '받는' in str(c) and '대표' not in str(c)), None)
            if not c_name: c_name = df.columns[12] # 못 찾으면 매출 표준 위치인 13번째 칸
        else:
            # 매입일 때는 '공급자' 쪽 '상호'를 찾습니다.
            c_name = next((c for c in df.columns if '상호' in str(c) and '받는' not in str(c) and '대표' not in str(c)), None)
            if not c_name: c_name = df.columns[6] # 못 찾으면 매입 표준 위치인 7번째 칸
            
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '품목' not in str(c)), df.columns[15])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '품목' not in str(c)), df.columns[16])

        # 데이터 변환
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['합계'] = df[c_supply] + df[c_tax]
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 2. 분류 작업
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            
            if "매출" in job_type:
                is_ansan = any(k in full_text for k in ['6114hojin', 'tpy1004', 'tpywater', '성남경찰서'])
                if is_ansan: ansan_list.append(row)
                else: incheon_list.append(row)
            else:
                # 매입 분류 로직
                if any(k in name_val for k in ['세무', '비즈', 'tax']):
                    r_a, r_i = row.copy(), row.copy()
                    r_a[c_supply], r_a[c_tax], r_a['합계'] = row[c_supply]/2, row[c_tax]/2, row['합계']/2
                    r_i[c_supply], r_i[c_tax], r_i['합계'] = row[c_supply]/2, row[c_tax]/2, row['합계']/2
                    ansan_list.append(r_a); incheon_list.append(r_i)
                elif any(k in name_val for k in ['kt', '케이티', '전화']):
                    st.info(f"📞 공동요금: {row[c_name]} (총 {row[c_supply]:,.0f}원)")
                    ansan_v = st.number_input(f"ㄴ {row[c_name]} 안산분 공급가액?", 0.0, float(row[c_supply]), float(row[c_supply]/2), key=f"kt_{idx}")
                    r_a, r_i = row.copy(), row.copy()
                    r_a[c_supply], r_a[c_tax], r_a['합계'] = ansan_v, ansan_v*0.1, ansan_v*1.1
                    r_i[c_supply], r_i[c_tax], r_i['합계'] = row[c_supply]-ansan_v, (row[c_supply]-ansan_v)*0.1, (row[c_supply]-ansan_v)*1.1
                    ansan_list.append(r_a); incheon_list.append(r_i)
                elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                    ansan_list.append(row)
                else:
                    incheon_list.append(row)

        # 3. 정리 및 출력
        def format_df(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_cols = [c_date, c_name, c_supply, c_tax, '합계']
            res_df = temp[display_cols].copy()
            
            final_rows = []
            for month, group in res_df.groupby(res_df[c_date].apply(lambda x: pd.to_datetime(x).month)):
                final_rows.append(group)
                sub = pd.DataFrame([{c_date: f"{int(month)}월 소계", c_name: "", c_supply: group[c_supply].sum(), c_tax: group[c_tax].sum(), '합계': group['합계'].sum()}])
                final_rows.append(sub)
            
            grand = pd.DataFrame([{c_date: "총 계", c_name: "", c_supply: res_df[c_supply].sum(), c_tax: res_df[c_tax].sum(), '합계': res_df['합계'].sum()}])
            final_rows.append(grand)
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = format_df(ansan_list)
        incheon_final = format_df(incheon_list)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 최종 정산내역 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_결과.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
