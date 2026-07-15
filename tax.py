import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.9.1)")
st.caption("안정적인 Ver 9.4 엔진 위에 KT 소액 강제 입력 기능만 정밀 이식했습니다.")

st.sidebar.header("⚙️ 정산 설정")
job_type = st.sidebar.radio("작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 (소액 시 변경)")
kt_threshold = st.sidebar.number_input("소액 기준 (공급가액)", value=55000)
kt_new_supply = st.sidebar.number_input("변경할 공급가액 (0: 원본 유지)", value=0)

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 및 헤더 찾기 (Ver 9.4 엔진)
        df_raw = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file)
        
        # 2. 컬럼명 정규화
        df_raw.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df_raw.columns]
        df = df_raw.copy()

        # 3. 매핑 (Ver 9.4 안정 로직)
        c_date = next((c for c in df.columns if '작성일자' in c or '일자' in c), df.columns[1])
        if job_type == "🛒 매입": c_name = next((c for c in df.columns if '상호' in c or '공급자상호' in c), df.columns[3])
        elif job_type == "💰 매출": c_name = next((c for c in df.columns if '상호1' in c or '공급받는자상호' in c), df.columns[3])
        else: c_name = next((c for c in df.columns if '가맹점' in c or '상호' in c), df.columns[3])
        
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1])

        # 4. 금액 정제
        def clean(val):
            try: return float(str(val).replace(',','').replace('원','').replace('"','').strip())
            except: return 0.0
            
        df[c_supply] = df[c_supply].apply(clean)
        df[c_tax] = df[c_tax].apply(clean)

        ansan_list, incheon_list = [], []
        for idx, row in df.iterrows():
            name_str = str(row[c_name])
            
            # 5. 분배 및 KT 소액 입력 로직
            is_split = False
            if any(k in name_str for k in ['진솔법무사', '비즈택스']): is_split = True
            elif '혜성환경' in name_str and '0511' in str(row[c_date]): is_split = True
            elif '케이티' in name_str or 'KT' in name_str:
                if row[c_supply] < kt_threshold:
                    if kt_new_supply > 0:
                        row[c_supply] = float(kt_new_supply)
                        row[c_tax] = float(kt_new_supply) * 0.1
                    is_split = True
            
            if is_split:
                r1, r2 = row.copy(), row.copy()
                r1[c_supply], r2[c_supply] = row[c_supply]/2, row[c_supply]/2
                r1[c_tax], r2[c_tax] = row[c_tax]/2, row[c_tax]/2
                ansan_list.append(r1); incheon_list.append(r2)
            else:
                if '남상민' in name_str or any(k in name_str for k in ['성남수정','성남경찰서']): ansan_list.append(row)
                else: incheon_list.append(row)

        st.success("✅ 정산 완료!")
        st.dataframe(pd.DataFrame(ansan_list)[[c_date, c_name, c_supply, c_tax]])
    except Exception as e:
        st.error(f"🚨 오류: {e}")
