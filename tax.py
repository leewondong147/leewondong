import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 7.1)")

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
            row_vals = [str(v) for v in df_raw.iloc[i].values]
            row_str = "".join(row_vals)
            if '작성일자' in row_str and '공급가액' in row_str and '세액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        c_date = next((c for c in df.columns if '작성일자' in str(c)), df.columns[0])
        c_name = next((c for c in df.columns if '상호' in str(c) and '받는' not in str(c)), df.columns[6])
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '품목' not in str(c)), df.columns[15])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '품목' not in str(c)), df.columns[16])

        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            supply_val = float(row[c_supply])
            tax_val = float(row[c_tax])

            if any(k in name_val for k in ['세무', '비즈', 'tax']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            elif any(k in name_val for k in ['kt', '케이티', '전화']):
                ansan_v = st.number_input(f"📞 {row[c_name]} ({supply_val:,.0f}원) 안산분?", 0.0, float(supply_val), float(supply_val/2), key=f"kt_{idx}")
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        def finalize_report(data_list):
            if not data_list: return pd.DataFrame()
            temp_df = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            final_rows = []
            for month, group in temp_df.groupby('월'):
                final_rows.append(group)
                sub_row = {col: "" for col in temp_df.columns}
                sub_row[c_name], sub_row[c_supply], sub_row[c_tax] = f"--- {int(month)}월 소계 ---", group[c_supply].sum(), group[c_tax].sum()
                final_rows.append(pd.DataFrame([sub_row]))
            grand_row = {col: "" for col in temp_df.columns}
            grand_row[c_name], grand_row[c_supply], grand_row[c_tax] = "=== 전체 총 합계 ===", temp_df[c_supply].sum(), temp_df[c_tax].sum()
            final_rows.append(pd.DataFrame([grand_row]))
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = finalize_report(ansan_list)
        incheon_final = finalize_report(incheon_list)

        # 엑셀 파일 생성 로직
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success("✅ 정산이 완료되었습니다!")
        st.download_button(
            label="📥 최종 정산 엑셀 다운로드 (통합본)",
            data=output.getvalue(),
            file_name="호진환경_최종_부가세정산.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        c1, c2 = st.columns(2)
        with c1: st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
