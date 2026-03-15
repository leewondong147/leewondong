import streamlit as st
import pandas as pd
import io

# 🌟 화면 기본 설정
st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.1 무적판)")
st.markdown("어떤 형식의 엑셀이든 제목 줄을 자동으로 찾아냅니다.")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.divider()

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # [핵심] 제목 줄 자동 찾기 로직
        raw_data = None
        if uploaded_file.name.endswith('.csv'):
            raw_data = pd.read_csv(uploaded_file, header=None)
        else:
            raw_data = pd.read_excel(uploaded_file, header=None)

        # '상호'나 '이메일'이 포함된 행을 찾아서 거기서부터 데이터를 읽음
        header_row = 0
        for i in range(len(raw_data)):
            row_str = "".join(raw_data.iloc[i].astype(str))
            if '상호' in row_str or '이메일' in row_str or '공급자명' in row_str:
                header_row = i
                break
        
        # 다시 제대로 읽기
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        st.success(f"✅ {header_row + 1}번째 줄에서 제목을 찾았습니다!")

        # 🔍 기둥 자동 매칭
        col_email = next((c for c in df.columns if '이메일' in str(c)), None)
        col_name = next((c for c in df.columns if '상호' in str(c) or '공급자명' in str(c)), None)
        col_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        col_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)

        if not all([col_supply, col_tax]):
            st.error("🚨 필수 기둥(공급가액, 세액)을 찾지 못했습니다. 파일을 확인해주세요.")
            st.stop()

        df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # ------------------------------------------
        # 💳 카드 / 💰 매출 / 🛒 매입 분류 (로직은 동일)
        # ------------------------------------------
        ansan_df, incheon_df = pd.DataFrame(), pd.DataFrame()

        if "카드" in job_type:
            ansan_df = df.iloc[0:0]
            incheon_df = df.copy()
        elif "매출" in job_type:
            is_ansan = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False) | \
                       df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
            ansan_df, incheon_df = df[is_ansan].copy(), df[~is_ansan].copy()
        else: # 매입
            is_ansan_basic = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False)
            is_biz = df[col_name].astype(str).str.contains('비즈텍스|비즈택스', na=False)
            is_kt = df[col_name].astype(str).str.contains('KT|케이티', na=False, case=False) & (df[col_supply] < 60000)
            
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

            # KT 분배
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

        # 다운로드 영역
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
        st.error(f"🚨 오류: {e}")
