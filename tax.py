import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 부가세 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 5.7 방탄판)")

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
            if '공급' in line and '세액' in line:
                skip_idx = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=skip_idx)
        else:
            df = pd.read_excel(uploaded_file, skiprows=skip_idx)

        # 3. 기둥 찾기 및 데이터 청소
        c_email = next((c for c in df.columns if '이메일' in str(c)), "이메일없음")
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자', '거래처', '고객'])), "상호없음")
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), df.columns[min(5, len(df.columns)-1)])
        c_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), df.columns[min(6, len(df.columns)-1)])

        # 모든 데이터를 글자로 바꿔서 에러 방지
        df[c_email] = df[c_email].astype(str).fillna("")
        df[c_name] = df[c_name].astype(str).fillna("")
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        ansan_list, incheon_list = [], []

        # 4. 분류 (매입 중심)
        if "매입" in job_type:
            for _, row in df.iterrows():
                name_val = row[c_name]
                email_val = row[c_email]
                supply_val = float(row[c_supply])
                tax_val = float(row[c_tax])

                # [검문 1] 비즈텍스 (5:5 분배)
                if any(k in name_val for k in ['비즈', '택스', 'TAX']):
                    r_a, r_i = row.copy(), row.copy()
                    r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                    r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                    ansan_list.append(r_a)
                    incheon_list.append(r_i)
                
                # [검문 2] KT 전화요금 (수동 분배)
                elif any(k in name_val for k in ['KT', '케이티', '전화']) and supply_val < 60000:
                    st.warning(f"📞 요금 확인: {name_val} ({supply_val:,.0f}원)")
                    ansan_v = st.number_input(f"ㄴ {name_val} 중 안산분 금액?", 0.0, supply_val, supply_val/2, key=f"k_{_}")
                    r_a, r_i = row.copy(), row.copy()
                    r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                    r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                    ansan_list.append(r_a)
                    incheon_list.append(r_i)
                
                # [검문 3] 본점 이메일 여부
                elif '6114hojin' in email_val.lower():
                    ansan_list.append(row)
                
                # [기타] 나머지는 인천
                else:
                    incheon_list.append(row)
        
        elif "매출" in job_type:
            for _, row in df.iterrows():
                email_val = row[c_email].lower() if c_email in df.columns else ""
                row_str = "".join(row.astype(str))
                if any(k in email_val for k in ['6114hojin', 'tpy1004', 'tpywater']) or '성남경찰서' in row_str:
                    ansan_list.append(row)
                else:
                    incheon_list.append(row)
        else: # 카드
            incheon_list = [row for _, row in df.iterrows()]

        ansan_df = pd.DataFrame(ansan_list)
        incheon_df = pd.DataFrame(incheon_list)

        # 5. 화면 출력 및 다운로드
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏢 안산 ({len(ansan_df)}건)")
            st.dataframe(ansan_df)
            if not ansan_df.empty:
                out = io.BytesIO()
                ansan_df.to_excel(out, index=False)
                st.download_button("📥 안산 엑셀", out.getvalue(), "ansan.xlsx")
        with col2:
            st.subheader(f"🏭 인천 ({len(incheon_df)}건)")
            st.dataframe(incheon_df)
            if not incheon_df.empty:
                out = io.BytesIO()
                incheon_df.to_excel(out, index=False)
                st.download_button("📥 인천 엑셀", out.getvalue(), "incheon.xlsx")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
