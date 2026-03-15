import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 7.3)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기
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

        # 기둥 매칭
        c_date = next((c for c in df.columns if '작성일자' in str(c)), df.columns[0])
        c_name = next((c for c in df.columns if '상호' in str(c) and '받는' not in str(c)), df.columns[6])
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '품목' not in str(c)), df.columns[15])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '품목' not in str(c)), df.columns[16])

        # 전처리 (숫자로 변환)
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['합계'] = df[c_supply] + df[c_tax]
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 2. 분류 로직
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            
            # [공동비용] 세무/비즈
            if any(k in name_val for k in ['세무', '비즈', 'tax']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax], r_a['합계'] = row[c_supply]/2, row[c_tax]/2, (row[c_supply]+row[c_tax])/2
                r_i[c_supply], r_i[c_tax], r_i['합계'] = row[c_supply]/2, row[c_tax]/2, (row[c_supply]+row[c_tax])/2
                ansan_list.append(r_a); incheon_list.append(r_i)
            
            # [공동비용] KT - 대표님 요청대로 다시 '공급가액' 입력 방식!
            elif any(k in name_val for k in ['kt', '케이티', '전화']):
                st.info(f"📞 공동요금: {row[c_name]} (총 공급가액: {row[c_supply]:,.0f}원)")
                # 입력창에 공급가액을 넣도록 변경
                ansan_supply_v = st.number_input(f"ㄴ {row[c_name]} 중 '안산분 공급가액'은?", 0.0, float(row[c_supply]), float(row[c_supply]/2), key=f"kt_{idx}")
                
                r_a, r_i = row.copy(), row.copy()
                # 안산분 계산
                r_a[c_supply] = ansan_supply_v
                r_a[c_tax] = ansan_supply_v * 0.1
                r_a['합계'] = r_a[c_supply] + r_a[c_tax]
                # 인천분 계산 (나머지)
                r_i[c_supply] = row[c_supply] - ansan_supply_v
                r_i[c_tax] = (row[c_supply] - ansan_supply_v) * 0.1
                r_i['합계'] = r_i[c_supply] + r_i[c_tax]
                
                ansan_list.append(r_a); incheon_list.append(r_i)
            
            # [일반] 안산 본점
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 3. PDF 스타일 정리 함수
        def format_for_excel(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_cols = [c_date, c_name, c_supply, c_tax, '합계']
            res_df = temp[display_cols].copy()
            
            final_rows = []
            for month, group in res_df.groupby(res_df[c_date].apply(lambda x: pd.to_datetime(x).month)):
                final_rows.append(group)
                sub_total = pd.DataFrame([{c_date: f"{int(month)}월 소계", c_name: "", c_supply: group[c_supply].sum(), c_tax: group[c_tax].sum(), '합계': group['합계'].sum()}])
                final_rows.append(sub_total)
            
            grand_total = pd.DataFrame([{c_date: "총 계", c_name: "", c_supply: res_df[c_supply].sum(), c_tax: res_df[c_tax].sum(), '합계': res_df['합계'].sum()}])
            final_rows.append(grand_total)
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = format_for_excel(ansan_list)
        incheon_final = format_for_excel(incheon_list)

        # 4. 다운로드
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success("✅ 정산 완료! 아래 버튼으로 통합 엑셀을 받으세요.")
        st.download_button("📥 최종 정산내역 엑셀 다운로드", output.getvalue(), "호진환경_부가세정산_최종.xlsx")
        
        col1, col2 = st.columns(2)
        with col1: st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with col2: st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
