import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.6)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.divider()

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 데이터 읽기
        if uploaded_file.name.endswith('.csv'):
            raw_data = pd.read_csv(uploaded_file, header=None)
        else:
            raw_data = pd.read_excel(uploaded_file, header=None)

        # 2. 제목 줄 찾기 (공급가액, 세액이 있는 줄)
        header_row = 0
        for i in range(len(raw_data)):
            row_str = "".join([str(val) for val in raw_data.iloc[i].values])
            if '공급' in row_str and '세액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 기둥 찾기
        col_email = next((c for c in df.columns if '이메일' in str(c)), None)
        col_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자명', '거래처', '성명'])), None)
        col_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        col_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)

        # 숫자 변환
        df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        ansan_df, incheon_df = pd.DataFrame(), pd.DataFrame()

        # --- 매입 분류 (이 부분이 핵심!) ---
        if "매입" in job_type:
            # 1. 비즈텍스 찾기 (이름에 '비즈' 혹은 'TAX' 혹은 '택스' 포함되면 무조건!)
            is_biz = df[col_name].astype(str).str.contains('비즈|택스|TAX', na=False, case=False)
            
            # 2. KT 찾기 (이름에 'KT', '케이티', '전화' 포함되고 6만원 미만이면 무조건!)
            is_kt = df[col_name].astype(str).str.contains('KT|케이티|전화', na=False, case=False) & (df[col_supply] < 60000)
            
            # 3. 기본 안산 이메일 (6114hojin)
            is_ansan_email = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False) if col_email else pd.Series([False]*len(df))
            
            # 분류 시작
            ansan_df = df[is_ansan_email & ~is_biz & ~is_kt].copy()
            incheon_df = df[~is_ansan_basic & ~is_biz & ~is_kt].copy() if col_email else df[~is_biz & ~is_kt].copy()

            # [물어보기] 비즈텍스 5:5 자동 분배
            biz_items = df[is_biz]
            if not biz_items.empty:
                st.info(f"✨ 기장료(비즈텍스 등) 관련 항목 {len(biz_items)}건을 찾아 5:5로 나눕니다.")
                for _, row in biz_items.iterrows():
                    r_a, r_i = row.copy(), row.copy()
                    r_a[col_supply], r_a[col_tax] = row[col_supply]/2, row[col_tax]/2
                    r_i[col_supply], r_i[col_tax] = row[col_supply]/2, row[col_tax]/2
                    ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                    incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

            # [물어보기] KT 요금 수동 분배
            kt_items = df[is_kt]
            if not kt_items.empty:
                st.warning(f"📞 공동 요금(KT 등) {len(kt_items)}건의 안산 금액을 입력해주세요.")
                for i, row in kt_items.iterrows():
                    total = float(row[col_supply])
                    ansan_v = st.number_input(f"👉 {row[col_name]} ({total:,.0f}원) 중 '안산' 공급가액은?", 0.0, total, total/2, key=f"kt_{i}")
                    r_a, r_i = row.copy(), row.copy()
                    r_a[col_supply], r_a[col_tax] = ansan_v, ansan_v * 0.1
                    r_i[col_supply], r_i[col_tax] = total-ansan_v, (total-ansan_v)*0.1
                    ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                    incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

        elif "매출" in job_type:
            # (매출 로직 동일)
            is_ansan = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False) | \
                       df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
            ansan_df, incheon_df = df[is_ansan].copy(), df[~is_ansan].copy()
        
        else: # 카드
            ansan_df, incheon_df = df.iloc[0:0], df.copy()

        # 다운로드 화면
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
        st.error(f"🚨 오류 발생: {e}")
