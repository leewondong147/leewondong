import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.5)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.divider()

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 전체 읽기
        if uploaded_file.name.endswith('.csv'):
            raw_data = pd.read_csv(uploaded_file, header=None)
        else:
            raw_data = pd.read_excel(uploaded_file, header=None)

        # 2. 진짜 제목 줄 찾기 (데이터가 시작되는 지점)
        header_row = 0
        for i in range(len(raw_data)):
            row_values = [str(val) for val in raw_data.iloc[i].values]
            row_str = "".join(row_values)
            # '공급' 혹은 '금액' 혹은 '세액' 이라는 단어가 보이면 거기가 제목줄입니다.
            if any(k in row_str for k in ['공급', '금액', '세액', '합계']):
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 🔍 기둥 이름 매칭 (매우 유연하게 검색)
        def find_col(keywords, exclude=None):
            for c in df.columns:
                c_str = str(c)
                if any(k in c_str for k in keywords):
                    if exclude and any(e in c_str for e in exclude):
                        continue
                    return c
            return None

        col_email = find_col(['이메일', 'Email'])
        col_name = find_col(['상호', '공급자', '거래처', '고객', '성명'])
        col_supply = find_col(['공급가액', '공급가', '금액', '가액'], exclude=['합계', '총액'])
        col_tax = find_col(['세액', '부가세', '세'], exclude=['합계', '총액'])

        # 만약 그래도 못 찾으면? 첫 번째 숫자 형태의 기둥을 임의로 지정 (비상용)
        if not col_supply: col_supply = df.columns[min(len(df.columns)-1, 5)]
        if not col_tax: col_tax = df.columns[min(len(df.columns)-1, 6)]

        # 숫자 변환
        df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        st.success(f"✅ 데이터를 성공적으로 읽었습니다! (제목 줄: {header_row + 1}행)")

        ansan_df, incheon_df = pd.DataFrame(), pd.DataFrame()

        # --- 분류 로직 ---
        if "카드" in job_type:
            ansan_df, incheon_df = df.iloc[0:0], df.copy()
        
        elif "매출" in job_type:
            # 이메일 혹은 상호로 안산 분류
            is_ansan_email = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False) if col_email else pd.Series([False]*len(df))
            is_seongnam = df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
            is_ansan = is_ansan_email | is_seongnam
            ansan_df, incheon_df = df[is_ansan].copy(), df[~is_ansan].copy()

        else: # 매입
            is_ansan_basic = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False) if col_email else pd.Series([False]*len(df))
            is_biz = df[col_name].astype(str).str.contains('비즈텍스|비즈택스', na=False) if col_name else pd.Series([False]*len(df))
            is_kt = (df[col_name].astype(str).str.contains('KT|케이티', na=False, case=False) & (df[col_supply] < 60000)) if col_name else pd.Series([False]*len(df))
            
            ansan_df = df[is_ansan_basic & ~is_biz & ~is_kt].copy()
            incheon_df = df[~is_ansan_basic & ~is_biz & ~is_kt].copy()

            # 비즈텍스 분배
            biz_df = df[is_biz].copy()
            for _, row in biz_df.iterrows():
                r_a, r_i = row.copy(), row.copy()
                r_a[col_supply], r_a[col_tax] = row[col_supply]/2, row[col_tax]/2
                r_i[col_supply], r_i[col_tax] = row[col_supply]/2, row[col_tax]/2
                ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

            # KT 요금 수동 입력
            kt_df = df[is_kt].copy()
            if not kt_df.empty:
                for i, row in kt_df.iterrows():
                    total = float(row[col_supply])
                    ansan_v = st.number_input(f"📞 {row[col_name]} ({total:,.0f}원) 중 안산분?", 0.0, total, total/2, key=f"k{i}")
                    r_a, r_i = row.copy(), row.copy()
                    r_a[col_supply], r_a[col_tax] = ansan_v, ansan_v * 0.1
                    r_i[col_supply], r_i[col_tax] = total-ansan_v, (total-ansan_v)*0.1
                    ansan_df = pd.concat([ansan_df, pd.DataFrame([r_a])])
                    incheon_df = pd.concat([incheon_df, pd.DataFrame([r_i])])

        # 결과 출력
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏢 안산 - {len(ansan_df)}건")
            st.dataframe(ansan_df)
            if not ansan_df.empty:
                out = io.BytesIO()
                ansan_df.to_excel(out, index=False)
                st.download_button("📥 안산 엑셀 다운로드", out.getvalue(), "ansan.xlsx")
        with col2:
            st.subheader(f"🏭 인천 - {len(incheon_df)}건")
            st.dataframe(incheon_df)
            if not incheon_df.empty:
                out = io.BytesIO()
                incheon_df.to_excel(out, index=False)
                st.download_button("📥 인천 엑셀 다운로드", out.getvalue(), "incheon.xlsx")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
