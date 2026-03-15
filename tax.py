import streamlit as st
import pandas as pd
import io

# 🌟 화면 기본 설정
st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 5.0 최종)")
st.markdown("매입/매출/카드 정산 통합 시스템입니다. 홈택스 원본 파일을 그대로 올려주세요.")

# 🎛️ 작업 종류 선택
job_type = st.radio("👇 어떤 자료를 작업하실 건가요?", [
    "🛒 매입 세금계산서 (돈 쓸 때)", 
    "💰 매출 세금계산서 (돈 벌 때)",
    "💳 법인카드 사용내역 (전부 지점)"
])
st.divider()

uploaded_file = st.file_uploader(f"📂 {job_type.split(' ')[1]} 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (카드 8줄, 매입/매출 4줄 건너뜀)
        skip = 8 if "카드" in job_type else 4
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=skip)
        else:
            # xls, xlsx 모두 대응 (엔진 자동 선택)
            df = pd.read_excel(uploaded_file, skiprows=skip)
            
        st.success("✅ 파일 읽기 성공!")

        # 2. 기둥 이름 자동 찾기 (유연하게 검색)
        col_email = next((c for c in df.columns if '이메일' in str(c)), None)
        col_name = next((c for c in df.columns if '상호' in str(c) or '공급자명' in str(c)), None)
        col_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        col_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)

        # 3. 데이터 정제 (콤마 제거 및 숫자로 변환)
        if col_supply and col_tax:
            df[col_supply] = pd.to_numeric(df[col_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            df[col_tax] = pd.to_numeric(df[col_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # ------------------------------------------
        # 💳 법인카드 로직 (전부 지점)
        # ------------------------------------------
        if "카드" in job_type:
            ansan_df = df.iloc[0:0].copy()
            incheon_df = df.copy()
            st.info("💡 법인카드 내역은 100% 인천(지점)으로 분류되었습니다.")

        # ------------------------------------------
        # 💰 매출 로직 (본점 이메일 3종 + 성남경찰서)
        # ------------------------------------------
        elif "매출" in job_type:
            if col_email:
                # 이메일 조건 (대소문자 구분 없이)
                is_ansan_email = df[col_email].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False)
                # 성남경찰서 조건 (전체 텍스트에서 검색)
                is_seongnam = df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
                
                is_ansan = is_ansan_email | is_seongnam
                ansan_df = df[is_ansan].copy()
                incheon_df = df[~is_ansan].copy()
            else:
                st.error("🚨 이메일 기둥을 찾을 수 없습니다.")
                st.stop()

        # ------------------------------------------
        # 🛒 매입 로직 (기장료/KT 분배)
        # ------------------------------------------
        elif "매입" in job_type:
            if col_email and col_name:
                # 기본 안산 이메일 분류
                is_ansan_email = df[col_email].astype(str).str.contains('6114hojin', na=False, case=False)
                
                # 비즈텍스(기장료) 찾기
                is_biz = df[col_name].astype(str).str.contains('비즈텍스|비즈택스', na=False)
                
                # KT 전화요금 찾기 (상호에 KT가 있고 6만원 미만인 경우)
                is_kt = df[col_name].astype(str).str.contains('KT|케이티', na=False, case=False) & (df[col_supply] < 60000)
                
                # 순수 안산/인천 (공동 요금 제외)
                ansan_df = df[is_ansan_email & ~is_biz & ~is_kt].copy()
                incheon_df = df[~is_ansan_email & ~is_biz & ~is_kt].copy()
                
                # [분배] 비즈텍스 5:5 자동 분배
                biz_df = df[is_biz].copy()
                if not biz_df.empty:
                    for _, row in biz_df.iterrows():
                        row_a, row_i = row.copy(), row.copy()
                        row_a[col_supply], row_a[col_tax] = row[col_supply]/2, row[col_tax]/2
                        row_i[col_supply], row_i[col_tax] = row[col_supply]/2, row[col_tax]/2
                        ansan_df = pd.concat([ansan_df, pd.DataFrame([row_a])])
                        incheon_df = pd.concat([incheon_df, pd.DataFrame([row_i])])
                    st.info("💡 비즈텍스 기장료가 50:50으로 분배되었습니다.")

                # [분배] KT 요금 수동 분배
                kt_df = df[is_kt].copy()
                if not kt_df.empty:
                    st.warning("⚠️ 공동 KT 요금이 발견되었습니다. 안산 금액을 입력하세요.")
                    for i, row in kt_df.iterrows():
                        total = float(row[col_supply])
                        ansan_val = st.number_input(f"👉 {row[col_name]} ({total:,.0f}원) 중 안산 공급가액?", 0.0, total, total/2, key=f"kt_{i}")
                        
                        row_a, row_i = row.copy(), row.copy()
                        row_a[col_supply], row_a[col_tax] = ansan_val, ansan_val * 0.1
                        row_i[col_supply], row_i[col_tax] = total - ansan_val, (total - ansan_val) * 0.1
                        ansan_df = pd.concat([ansan_df, pd.DataFrame([row_a])])
                        incheon_df = pd.concat([incheon_df, pd.DataFrame([row_i])])
            else:
                st.error("🚨 필수 기둥을 찾을 수 없습니다.")
                st.stop()

        # ------------------------------------------
        # 🏁 최종 결과 및 다운로드
        # ------------------------------------------
        st.divider()
        c1, c2 = st.columns(2)
        prefix = "카드" if "카드" in job_type else ("매출" if "매출" in job_type else "매입")
        
        with c1:
            st.subheader(f"🏢 안산(본점) - {len(ansan_df)}건")
            st.dataframe(ansan_df)
            if not ansan_df.empty:
                out = io.BytesIO()
                ansan_df.to_excel(out, index=False, engine='openpyxl')
                st.download_button("📥 안산 엑셀 다운로드", out.getvalue(), f"안산_{prefix}.xlsx")

        with c2:
            st.subheader(f"🏭 인천(지점) - {len(incheon_df)}건")
            st.dataframe(incheon_df)
            if not incheon_df.empty:
                out2 = io.BytesIO()
                incheon_df.to_excel(out2, index=False, engine='openpyxl')
                st.download_button("📥 인천 엑셀 다운로드", out2.getvalue(), f"인천_{prefix}.xlsx")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
