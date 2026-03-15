import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.4)")

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

        # 2. 진짜 제목 줄 찾기
        header_row = 0
        for i in range(len(raw_data)):
            row_values = [str(val) for val in raw_data.iloc[i].values]
            row_str = "".join(row_values)
            if '공급가액' in row_str and '세액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 기둥 이름 매칭 및 데이터 정리
        col_email = next((c for c in df.columns if '이메일' in str(c)), None)
        col_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자명', '거래처', '고객명'])), None)
        col_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        col_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)

        if not col_supply or not col_tax:
            st.error("🚨 공급가액 또는 세액 기둥을 찾지 못했습니다.")
            st.stop()

        # 숫자 변환 및 빈칸 처리
        df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        if col_email:
            df[col_email] = df[col_email].fillna("")
        if col_name:
            df[col_name] = df[col_name].fillna("")

        st.success(f"✅ {header_row + 1}행에서 데이터를 성공적으로 읽어왔습니다!")

        ansan_df, incheon_df = pd.DataFrame(), pd.DataFrame()

        # ------------------------------------------
        # 분류 로직 (카드/매출/매입)
        # ------------------------------------------
        if "카드" in job_type:
            ansan_df, incheon_df = df.iloc[0:0], df.copy()
        
        elif "매출" in job_type:
            # 이메일 체크 (이메일 기둥이 있을 때만)
            if col_email:
                is_ansan_email = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False)
            else:
                is_ansan_email = pd.Series([False] * len(df))
            
            # 상호 전체에서 '성남경찰서' 검색
            is_seongnam = df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
            
            is_ansan = is_ansan_email | is_seongnam
            ansan_df, incheon_df = df[is_ansan].copy(), df[~is_ansan].copy()

        else: # 매입
            # 이메일 체크
            if col_email:
                is_ansan_basic = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False)
            else:
                is_ansan_basic = pd.Series([False] * len(df))
                
            # 비즈텍스/KT 체크
            is_biz = df[col_name].astype(str).str.contains('비즈텍스|비즈택스', na=False) if col_name else pd.Series([False]*len(df))
            is_kt = (df[col_name].astype(str).str.contains('KT|케이티', na=False, case=False) & (df[col_supply] < 60000)) if col_name else pd.Series([False]*len(df))
            
            ansan_df = df[is_ansan_basic & ~is_biz & ~is_kt].copy()
            incheon_df = df[~is_ansan_basic & ~is_biz & ~is_kt].copy()

            # 분배 로직
            biz_df = df[is_biz].copy()
            for _, row in biz_df.iterrows():
                for target_df in [ansan_df, incheon_df]:
                    new_row = row.copy()
                    new_row[col_supply], new_row[col_tax] = row[col_supply]/2, row[col_tax]/2
                    if target_df is ansan_df: ansan_df = pd.concat([ansan_df, pd.DataFrame([new_row])])
                    else: incheon_df = pd.concat([incheon_df, pd.DataFrame([new_row])])

            kt_df = df[is_kt].copy()
            if not kt_df.empty:
                for i, row in kt_df.iterrows():
                    total = float(row[col_supply])
                    ansan_v = st.number_input(f"📞 {row[col_name]} ({total:,.0f}원) 중 안산분?", 0.0, total, total/2, key=f"k{i}")
                    
                    row_a, row_i = row.copy(), row.copy()
                    row_a[col_supply], row_a[col_tax] = ansan_v, ansan_v * 0.1
                    row_i[col_supply], row_i[col_tax] = total-ansan_v, (total-ansan_v)*0.1
                    ansan_df = pd.concat([ansan_df, pd.DataFrame([row_a])])
                    incheon_df = pd.concat([incheon_df, pd.DataFrame([row_i])])

        # 결과 출력
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏢 안산 - {len(ansan_df)}건")
            st.dataframe(ansan_df)
            if not ansan_df.empty:
                out = io.BytesIO()
                ansan_df.to_excel(out, index=False)
                st.download_button("📥 안산 다운로드", out.getvalue(), "ansan.xlsx")
        with col2:
            st.subheader(f"🏭 인천 - {len(incheon_df)}건")
            st.dataframe(incheon_df)
            if not incheon_df.empty:
                out = io.BytesIO()
                incheon_df.to_excel(out, index=False)
                st.download_button("📥 인천 다운로드", out.getvalue(), "incheon.xlsx")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
