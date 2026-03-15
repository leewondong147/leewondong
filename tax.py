import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 7.0)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 및 진짜 데이터 시작점 찾기
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        header_row = 0
        for i in range(len(df_raw)):
            row_vals = [str(v) for v in df_raw.iloc[i].values]
            row_str = "".join(row_vals)
            # '작성일자', '공급가액', '세액'이 모두 있는 줄이 진짜 제목줄입니다.
            if '작성일자' in row_str and '공급가액' in row_str and '세액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 2. 기둥 이름 정밀 매칭 (소계가 비지 않도록 숫자를 정확히 잡습니다)
        c_date = next((c for c in df.columns if '작성일자' in str(c)), df.columns[0])
        c_name = next((c for c in df.columns if '상호' in str(c) and '받는' not in str(c)), df.columns[6])
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '품목' not in str(c)), df.columns[15])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '품목' not in str(c)), df.columns[16])

        # 숫자 변환 (콤마 제거)
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 3. 분류 작업 (세무법인 & KT 질문)
        st.info("💡 공동 비용(세무법인, KT) 감지 시 아래에 질문창이 나타납니다.")
        
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            supply_val = float(row[c_supply])
            tax_val = float(row[c_tax])

            # [핵심 변경] 상호명에 '세무' 혹은 '비즈'가 들어가면 무조건 기장료로 보고 5:5 분배
            if any(k in name_val for k in ['세무', '비즈', 'tax']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            
            # [공동] KT/전화요금 질문
            elif any(k in name_val for k in ['kt', '케이티', '전화']):
                ansan_v = st.number_input(f"📞 {row[c_name]} ({supply_val:,.0f}원) 안산분 금액?", 0.0, float(supply_val), float(supply_val/2), key=f"kt_{idx}")
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                ansan_list.append(r_a)
                incheon_list.append(r_i)

            # [안산] 본점 분류 (6114, 성남경찰서 등)
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            
            # [인천] 나머지
            else:
                incheon_list.append(row)

        # 4. 소계 및 전체 합계 완성 함수
        def finalize_report(data_list):
            if not data_list: return pd.DataFrame()
            temp_df = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            final_rows = []
            for month, group in temp_df.groupby('월'):
                final_rows.append(group)
                # 소계 계산
                s_sum, t_sum = group[c_supply].sum(), group[c_tax].sum()
                sub_row = {col: "" for col in temp_df.columns}
                sub_row[c_name] = f"--- {int(month)}월 소계 ---"
                sub_row[c_supply] = s_sum
                sub_row[c_tax] = t_sum
                final_rows.append(pd.DataFrame([sub_row]))
            
            # 총 합계 계산
            total_s, total_t = temp_df[c_supply].sum(), temp_df[c_tax].sum()
            grand_row = {col: "" for col in temp_df.columns}
            grand_row[c_name] = "=== 전체 총 합계 ==="
            grand_row[c_supply] = total_s
            grand_row[c_tax] = total_t
            final_rows.append(pd.DataFrame([grand_row]))
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = finalize_report(ansan_list)
        incheon_final = finalize_report(incheon_list)

        # 5. 화면 표시 및 다운로드
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏢 안산 본점")
            st.dataframe(ansan_final)
            if not ansan_final.empty:
                st.download_button("📥 안산 엑셀", ansan_final.to_csv(index=False).encode('utf-8-sig'), "ansan_final.csv")
        with c2:
            st.subheader("🏭 인천 지점")
            st.dataframe(incheon_final)
            if not incheon_final.empty:
                st.download_button("📥 인천 엑셀", incheon_final.to_csv(index=False).encode('utf-8-sig'), "incheon_final.csv")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
