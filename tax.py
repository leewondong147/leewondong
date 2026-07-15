import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.7 동적 분배 비율 조절판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.7)")
st.caption("고정된 50% 분배를 폐기하고, 매월 변경되는 안산/인천 분배 비율을 화면에서 직접 조절할 수 있는 동적 스플릿 엔진을 탑재했습니다.")

# ==========================================
# ⚙️ [사이드바] 커스텀 설정 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()

# 🚨 [신규 장착] 매월 변경되는 분배 비율 슬라이더
st.sidebar.subheader("⚖️ 거래처 분배 비율 설정")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)
incheon_ratio = 100 - ansan_ratio
st.sidebar.caption(f"👉 현재 설정: 안산 **{ansan_ratio}%** / 인천 **{incheon_ratio}%**")

st.sidebar.divider()

st.sidebar.subheader("📞 주식회사 KT 요금 설정")
kt_threshold = st.sidebar.number_input("이 금액 미만일 경우 '소액'으로 간주 (공급가액 기준)", value=55000, step=1000)
kt_new_supply = st.sidebar.number_input("👉 소액일 경우 변경할 공급가액 (0원이면 원본 유지)", value=0, step=1000)
st.sidebar.caption("※ 조건 충족 시, 위에서 설정한 비율대로 안산과 인천에 분배됩니다.")

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구] 무결점 수치 및 날짜 추출기
# ==========================================
def clean_value_secure(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try: return float(val_str)
    except: return 0.0

def parse_flexible_date(series):
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    cleaned = cleaned.str.replace('년', '-').str.replace('월', '-').str.replace('일', '')
    return pd.to_datetime(cleaned, errors='coerce')

if uploaded_file is not None:
    try:
        # 1. 파일 읽기
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        # 2. 제목 줄(Header) 강제 사냥 로직
        header_row = 0
        found_header = False
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(map(str, df_raw.iloc[i].fillna('').values))
            cleaned_row = re.sub(r'[^가-힣a-zA-Z0-9]', '', row_str)
            if ('승인번호' in cleaned_row and '공급가액' in cleaned_row) or \
               ('작성일자' in cleaned_row and '공급가액' in cleaned_row) or \
               ('일자' in cleaned_row and '상호' in cleaned_row):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        df.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df.columns]

        # 3. 매핑 로직
        c_date = next((c for c in df.columns if '작성일자' in c), None)
        if not c_date: c_date = next((c for c in df.columns if '일자' in c), df.columns[1] if len(df.columns)>1 else df.columns[0])

        if job_type == "🛒 매입":
            c_name = next((c for c in df.columns if c == '상호' or '공급자상호' in c), None)
        elif job_type == "💰 매출":
            c_name = next((c for c in df.columns if c == '상호1' or '공급받는자상호' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c), None)
        else:
            c_name = next((c for c in df.columns if '가맹점' in c or '상호' in c or '거래처' in c), None)
            
        if not c_name: c_name = df.columns[6] if len(df.columns) > 6 else df.columns[2]

        c_supply = next((c for c in df.columns if '공급가액' in c), None)
        if not c_supply: c_supply = next((c for c in df.columns if '합계' in c or '금액' in c), df.columns[-2] if len(df.columns)>2 else df.columns[-1])
        c_tax = next((c for c in df.columns if '세액' in c), None)

        # 4. 데이터 파싱
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        if c_tax: df[c_tax] = df[c_tax].apply(clean_value_secure)
        else:
            df['임시세액'] = df[c_supply] * 0.1
            c_tax = '임시세액'

        df['합계'] = df[c_supply] + df[c_tax]
        
        parsed_dates = parse_flexible_date(df[c_date])
        df['월'] = parsed_dates.dt.month.fillna(0).astype(int)
        df['일'] = parsed_dates.dt.day.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # ==========================================
        # 🚨 5. [동적 비율 분배] 매월 변경 가능한 스플릿 로직
        # ==========================================
        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            name_str = str(row[c_name]).replace(" ", "").lower()
            
            is_split_target = False
            
            # [조건 1] 진솔법무사 & 비즈택스
            if '진솔법무사' in name_str or '비즈택스' in name_str:
                is_split_target = True
                
            # [조건 2] 혜성환경 (5월 11일 한정)
            elif '혜성환경' in name_str and row['월'] == 5 and row['일'] == 11:
                is_split_target = True
                
            # [조건 3] 주식회사 KT 소액
            elif '케이티' in name_str or 'kt' in name_str:
                if row[c_supply] < kt_threshold:
                    if kt_new_supply > 0:
                        row[c_supply] = float(kt_new_supply)
                        row[c_tax] = float(kt_new_supply) * 0.1
                        row['합계'] = row[c_supply] + row[c_tax]
                    is_split_target = True

            # 설정된 동적 비율(ansan_ratio)에 따라 분할
            if is_split_target:
                row_ansan = row.copy()
                row_incheon = row.copy()
                
                # 오차 방지를 위해 안산 본점 금액을 먼저 계산 (내림 처리)
                ansan_supply_val = np.floor(row[c_supply] * (ansan_ratio / 100.0))
                ansan_tax_val = np.floor(row[c_tax] * (ansan_ratio / 100.0))
                
                row_ansan[c_supply] = ansan_supply_val
                row_ansan[c_tax] = ansan_tax_val
                row_ansan['합계'] = ansan_supply_val + ansan_tax_val
                
                # 인천 지점은 총액에서 안산 본점 금액을 뺀 나머지를 정확히 가져감
                row_incheon[c_supply] = row[c_supply] - ansan_supply_val
                row_incheon[c_tax] = row[c_tax] - ansan_tax_val
                row_incheon['합계'] = row_incheon[c_supply] + row_incheon[c_tax]
                
                # 비율이 0%가 아닐 때만 각각의 리스트에 추가
                if ansan_ratio > 0:
                    ansan_list.append(row_ansan)
                if incheon_ratio > 0:
                    incheon_list.append(row_incheon)
                continue
                
            # --- [일반 조건] 안산 본점 / 인천 지점 일반 분류 ---
            if '남상민' in full_text:
                ansan_list.append(row)
            elif any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 6. 결과 정리 및 소계/총계 연산
        def format_df(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_df = pd.DataFrame()
            display_df['작성일자'] = temp[c_date]
            display_df['상호'] = temp[c_name]
            display_df['공급가액'] = temp[c_supply]
            display_df['세액'] = temp[c_tax]
            display_df['합계'] = temp['합계']
            
            final_rows = []
            temp_dates = parse_flexible_date(display_df['작성일자'])
            display_df['temp_month'] = temp_dates.dt.month.fillna(0).astype(int)
            
            for month, group in display_df.groupby('temp_month'):
                group_clean = group.drop(columns=['temp_month'])
                final_rows.append(group_clean)
                
                sub = pd.DataFrame([{
                    '작성일자': f"{int(month)}월 소계", 
                    '상호': "", 
                    '공급가액': group['공급가액'].sum(), 
                    '세액': group['세액'].sum(), 
                    '합계': group['합계'].sum()
                }])
                final_rows.append(sub)
            
            grand = pd.DataFrame([{
                '작성일자': "총 계", 
                '상호': "", 
                '공급가액': display_df['공급가액'].sum(), 
                '세액': display_df['세액'].sum(), 
                '합계': display_df['합계'].sum()
            }])
            final_rows.append(grand)
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = format_df(ansan_list)
        incheon_final = format_df(incheon_list)

        # 7. 다운로드 및 결과 출력
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 파일 형식이 평소와 다른지 확인해주세요.")
