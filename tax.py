import streamlit as st
import pandas as pd
import io

# 🌟 화면 기본 설정
st.set_page_config(page_title="호진환경 부가세 자동 분류기", layout="wide")
st.title("📊 (주)호진환경 부가세 자동 분류기 (Ver 4.0 완결판)")
st.markdown("매입/매출 세금계산서는 물론, **법인카드 내역(전액 지점)**까지 완벽하게 처리합니다!")

# 🎛️ 작업 종류 선택 스위치 (3가지로 늘어났습니다!)
job_type = st.radio("👇 어떤 자료를 작업하실 건가요?", [
    "🛒 매입 세금계산서 (돈 쓸 때)", 
    "💰 매출 세금계산서 (돈 벌 때)",
    "💳 법인카드 사용내역 (전부 지점)"
])
st.divider()

# 파일 올리기 버튼
uploaded_file = st.file_uploader(f"📂 {job_type.split(' ')[1]} 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # ==========================================
        # 💳 1. 법인카드 로직 (전액 인천 지점)
        # ==========================================
        if "카드" in job_type:
            # 카드 내역은 윗부분 쓸데없는 줄이 더 많을 수 있어서 대략 7~8줄을 건너뜁니다.
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, skiprows=8)
            else:
                df = pd.read_excel(uploaded_file, skiprows=8)
            
            st.success("✅ 법인카드 파일 읽기 성공!")
            
            # 카드는 무조건 안산 0건, 전부 인천!
            ansan_df = df.iloc[0:0].copy() # 텅 빈 안산 장부
            incheon_df = df.copy()         # 원본 그대로 100% 인천 장부
            
            st.info("💡 규칙에 따라 법인카드 내역은 100% 인천(지점) 장부로 배정되었습니다!")

        # ==========================================
        # 🛒💰 2. 매입/매출 세금계산서 로직
        # ==========================================
        else:
            # 매입/매출은 항상 4줄 건너뜀
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, skiprows=4)
            else:
                df = pd.read_excel(uploaded_file, skiprows=4)
                
            st.success(f"✅ 파일 읽기 성공! 분류 작업을 시작합니다...")

            # 🟢 매출 로직
            if "매출" in job_type:
                email_col = next((col for col in df.columns if '공급자 이메일' in str(col)), None)
                if email_col:
                    is_ansan_email = df[email_col].astype(str).str.contains('6114hojin|tpy1004|tpywater', na=False, case=False)
                    is_seongnam = df.astype(str).apply(lambda x: x.str.contains('성남경찰서')).any(axis=1)
                    
                    is_ansan = is_ansan_email | is_seongnam
                    ansan_df = df[is_ansan].copy()
                    incheon_df = df[~is_ansan].copy()
                    st.info("💡 매출 분류: 본점 이메일(3개) 및 성남경찰서(예외)는 안산, 나머지는 인천으로 쪼갰습니다!")
                else:
                    st.error("🚨 파일에서 '공급자 이메일' 칸을 찾을 수 없습니다. 매출 파일이 맞는지 확인해주세요.")
                    st.stop()

            # 🔵 매입 로직 (기장료/KT 분배)
            elif "매입" in job_type:
                email_col = next((col for col in df.columns if '공급받는자 이메일' in str(col) or '이메일' in str(col)), None)
                name_col = next((col for col in df.columns if '상호' in str(col)), None)
                supply_col = next((col for col in df.columns if '공급가액' in str(col) and '총' not in str(col)), None)
                tax_col = next((col for col in df.columns if '세액' in str(col) and '총' not in str(col)), None)

                if email_col and name_col and supply_col and tax_col:
                    df[supply_col] = pd.to_numeric(df[supply_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    df[tax_col] = pd.to_numeric(df[tax_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    
                    is_ansan_email = df[email_col].astype(str).str.contains('6114hojin', na=False, case=False)
                    is_biztex = df[name_col].astype(str).str.contains('비즈텍스', na=False) & (~is_ansan_email)
                    is_kt_common = df[name_col].astype(str).str.contains('KT', na=False) & (df[supply_col] < 60000) & (~is_ansan_email)
                    
                    ansan_df = df[is_ansan_email].copy()
                    incheon_df = df[(~is_ansan_email) & (~is_biztex) & (~is_kt_common)].copy()
                    
                    biztex_df = df[is_biztex].copy()
                    if not biztex_df.empty:
                        biztex_ansan, biztex_incheon = biztex_df.copy(), biztex_df.copy()
                        biztex_ansan[supply_col] /= 2
                        biztex_ansan[tax_col] /= 2
                        biztex_incheon[supply_col] /= 2
                        biztex_incheon[tax_col] /= 2
                        
                        ansan_df = pd.concat([ansan_df, biztex_ansan])
                        incheon_df = pd.concat([incheon_df, biztex_incheon])
                        st.info("💡 세무법인비즈텍스 기장료/부가세 50:50 분배 완료!")

                    kt_df = df[is_kt_common].copy()
                    if not kt_df.empty:
                        st.warning("⚠️ 이번 달 공동 KT 전화요금(5만원대)이 발견되었습니다! 안산(본점) 금액을 입력해주세요.")
                        for index, row in kt_df.iterrows():
                            total_supply = float(row[supply_col])
                            total_tax = float(row[tax_col])
                            
                            ansan_supply = st.number_input(
                                f"👉 총 공급가액 {total_supply:,.0f}원 중 안산 금액?", 
                                min_value=0.0, max_value=total_supply, value=total_supply/2, step=10.0, key=f"kt_{index}"
                            )
                            ansan_tax = ansan_supply * 0.1
                            
                            kt_ansan = row.to_frame().T
                            kt_ansan[supply_col], kt_ansan[tax_col] = ansan_supply, ansan_tax
                            ansan_df = pd.concat([ansan_df, kt_ansan])
                            
                            kt_incheon = row.to_frame().T
                            kt_incheon[supply_col], kt_incheon[tax_col] = total_supply - ansan_supply, total_tax - ansan_tax
                            incheon_df = pd.concat([incheon_df, kt_incheon])
                            
                        st.success("✅ KT 요금 분배 완료!")
                else:
                    st.error("🚨 필수 기둥을 찾을 수 없습니다.")
                    st.stop()

        # ==========================================
        # 🏁 공통: 최종 결과 화면 및 엑셀 다운로드
        # ==========================================
        st.divider()
        col1, col2 = st.columns(2)
        
        # 파일 저장할 때 이름 바꾸기 (카드내역, 매출장, 매입장)
        if "카드" in job_type:
            file_prefix = "카드내역"
        else:
            file_prefix = "매출장" if "매출" in job_type else "매입장"
        
        with col1:
            st.subheader(f"🏢 안산(본점) {file_prefix} - {len(ansan_df)}건")
            if not ansan_df.empty:
                st.dataframe(ansan_df)
                towrite = io.BytesIO()
                ansan_df.to_excel(towrite, index=False, engine='openpyxl')
                towrite.seek(0)
                st.download_button(label=f"📥 안산 {file_prefix} 다운로드", data=towrite, file_name=f"안산_{file_prefix}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.write("안산(본점)으로 배정된 내역이 없습니다.")
            
        with col2:
            st.subheader(f"🏭 인천(지점) {file_prefix} - {len(incheon_df)}건")
            if not incheon_df.empty:
                st.dataframe(incheon_df)
                towrite2 = io.BytesIO()
                incheon_df.to_excel(towrite2, index=False, engine='openpyxl')
                towrite2.seek(0)
                st.download_button(label=f"📥 인천 {file_prefix} 다운로드", data=towrite2, file_name=f"인천_{file_prefix}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.write("인천(지점)으로 배정된 내역이 없습니다.")

    except Exception as e:
        st.error(f"🚨 에러가 발생했습니다. 원인: {e}")
