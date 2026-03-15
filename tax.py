import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.2)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.divider()

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (제목 줄 자동 찾기)
        if uploaded_file.name.endswith('.csv'):
            raw_data = pd.read_csv(uploaded_file, header=None)
        else:
            raw_data = pd.read_excel(uploaded_file, header=None)

        header_row = 0
        for i in range(len(raw_data)):
            row_str = "".join(raw_data.iloc[i].astype(str))
            # '공급'이나 '세액' 혹은 '상호'가 있으면 제목 줄로 판단
            if any(k in row_str for k in ['상호', '공급', '세액', '이메일', '공급자명']):
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 2. 🔍 기둥 이름 초정밀 매칭 (글자 일부만 맞아도 OK)
        col_email = next((c for c in df.columns if '이메일' in str(c)), None)
        col_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자명', '거래처'])), None)
        # '공급'이라는 글자가 들어간 칸 중 '총'이나 '합계'가 아닌 것 우선
        col_supply = next((c for c in df.columns if '공급' in str(c) and '총' not in str(c)), None)
        col_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)

        # 만약 위 조건으로 못찾으면 그냥 '공급'이나 '세액' 들어간 첫번째 칸 선택
        if not col_supply: col_supply = next((c for c in df.columns if '공급' in str(c)), None)
        if not col_tax: col_tax = next((c for c in df.columns if '세액' in str(c)), None)

        if not col_supply or not col_tax:
            st.error(f"🚨 기둥을 못 찾았습니다. 현재 기둥들: {list(df.columns)}")
            st.info("💡 엑셀의 제목 이름(공급가액, 세액 등)이 어떻게 적혀있는지 확인이 필요합니다.")
            st.stop()

        st.success(f"✅ 제목 줄({header_row + 1}행)과 기둥들을 성공적으로 매칭했습니다!")

        # 3. 데이터 숫자 변환
        df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # --- 분류 로직 (이전과 동일) ---
        ansan_df, incheon_df = pd.DataFrame(), pd.DataFrame()

        if "카드" in job_type:
            ansan_df = df.iloc[0:0]
            incheon_df = df.copy()
        elif "매출" in job_type:
            is_ansan = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False) | \
                       df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
            ansan_df, incheon_df = df[is_ansan].copy(), df[~is_ansan].copy()
        else: # 매입
            is_ansan_basic = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False) if col_email else pd.Series([False]*len(df))
            is_biz = df[col_name].astype(str).str.contains('비즈텍스|비즈택스', na=False) if col_name else pd.Series([False]*len(df))
            is_kt = (df[col_name].astype(str).str.contains('KT|케이티', na=False, case=False) & (df[col_supply] < 60000)) if col_name else pd.Series([False]*len(df))
            
            ansan_df = df[is_ansan_basic & ~is_biz & ~is_kt].copy()
            incheon_df = df[~is_ansan_basic & ~is_biz & ~is_kt].copy()

            biz_df = df[is_biz].copy()
            for _, row in biz_df.iterrows():
                r_a, r_i = row.copy(), row.copy()
                r_a[col_supply], r_a[col_tax] = row[col_supply]/2, row[col_tax]/2
                r_i[col_supply], r_i[col_tax] = row[col_supply]/2, row[col_tax]/2
                ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

            kt_df = df[is_kt].copy()
            if not kt_df.empty:
                for i, row in kt_df.iterrows():
                    total = float(row[col_supply])
                    ansan_v = st.number_input(f"👉 {row[col_name]} ({total:,.0f}원) 안산분?", 0.0, total, total/2, key=f"k{i}")
                    r_a, r_i = row.copy(), row.copy()
                    r_a[col_supply], r_a[col_tax] = ansan_v, ansan_v * 0.1
                    r_i[col_supply], r_i[col_tax] = total-ansan_v, (total-ansan_v)*0.1
                    ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                    incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"🏢 안산 - {len(ansan_df)}건")
            st.dataframe(ansan_df)
            if not ansan_df.empty:
                out = io.BytesIO()
                ansan_df.to_excel(out, index=False)
                st.download_button("📥 안산 다운로드", out.getvalue(), "ansan.xlsx")
        with c2:
            st.subheader(f"🏭 인천 - {len(incheon_df)}건")
            st.dataframe(incheon_df)
            if not incheon_df.empty:
                out = io.BytesIO()
                incheon_df.to_excel(out, index=False)
                st.download_button("📥 인천 다운로드", out.getvalue(), "incheon.xlsx")

    except Exception as e:
        st.error(f"🚨 오류: {e}")
