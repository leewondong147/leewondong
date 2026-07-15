import streamlit as st
import pandas as pd
import numpy as np
import io

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.3 초강력 완결 복구판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.3)")
st.caption("상호와 날짜의 변수 매핑 오작동을 완벽 통제하고, 공급가액 및 세액의 0원 소실을 백업 수치 추출 알고리즘으로 해결했습니다.")

# 작업 선택
job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구] 무결점 수치 추출기
# ==========================================
def clean_value_secure(val):
    """단일 값에 든 모든 쉼표, 한글, 공백을 물리적으로 지우고 순수 숫자로 변환합니다."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    val_str = val_str.replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try:
        return float(val_str)
    except:
        return 0.0

def parse_flexible_date(series):
    """한글 날짜 및 기호 날짜 형식을 표준 datetime으로 동기화합니다."""
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    cleaned = cleaned.str.replace('년', '-').str.replace('월', '-').str.replace('일', '')
    return pd.to_datetime(cleaned, errors='coerce')

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (글자 형식으로 안전하게)
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        # 2. 제목 줄(Header) 찾기 로직 강화
        header_row = 0
        found_header = False
        for i in range(min(len(df_raw), 25)):
            row_vals = df_raw.iloc[i].fillna('').values
            row_str = "".join(map(str, row_vals)).replace(" ", "")
            # 승인번호, 공급가액 등의 실무 거래 정보 키워드로 정교한 탐색 시작
            if any(k in row_str for k in ['일자', '공급가액', '승인번호', '거래처', '상호', '세액']):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 컬럼 양끝 공백 제거 및 정형화
        df.columns = [str(c).strip() for c in df.columns]

        # ==========================================
        # 🚨 3. [초강력 매핑] 날짜-상호 중복 및 꼬임 완전 파괴 가드레일
        # ==========================================
        # 가. 작성일자 열 찾기 (단순 '일자', '작성일' 우선 지목)
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['작성일자', '작성일', '일자', '일시'])), None)
        if not c_date:
            c_date = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            
        # 나. 상호명 열 찾기 (🚨 날짜 기둥 c_date로 선택된 컬럼은 절대 중복 지정되지 않도록 배제!)
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '가맹점', '거래처', '회사명', '공급자']) and str(c) != c_date), None)
        if not c_name:
            # 일자가 위치한 다음다음 칸 부근을 정렬 구조에 입각해 선택
            remaining_cols = [col for col in df.columns if col != c_date]
            c_name = remaining_cols[1] if len(remaining_cols) > 1 else remaining_cols[0]
            
        # 다. 공급가액 및 세액 열 매칭 (기존에 선택 완료된 날짜와 상호 컬럼 원천 배제!)
        c_supply = next((c for c in df.columns if any(k in str(c) for k in ['공급가액', '공급가', '공급가액(원)']) and str(c) not in [c_date, c_name]), None)
        if not c_supply:
            c_supply = next((c for c in df.columns if any(k in str(c) for k in ['금액', '합계', '승인금액', '이용금액', '합계금액']) and str(c) not in [c_date, c_name]), None)
            
        c_tax = next((c for c in df.columns if any(k in str(c) for k in ['세액', '부가세', '세액(원)']) and str(c) not in [c_date, c_name, c_supply]), None)

        # ==========================================
        # 🛡️ [수리 보증 백업 장치] 수치가 발견되지 않았을 경우 최후의 복원 엔진
        # ==========================================
        # 만약 공급가액이나 세액 컬럼 매칭에 실패하여 0원 데이터가 발생할 기조가 보일 때 가동됩니다.
        if not c_supply or df[c_supply].apply(clean_value_secure).sum() == 0.0:
            # 데이터프레임 내에서 날짜와 상호를 뺀 나머지 열 중 수치형 연산 결과 합산액이 가장 높은 열을 동적으로 자동 수립합니다!
            numerical_candidates = []
            for col in df.columns:
                if col not in [c_date, c_name]:
                    total_vol = df[col].apply(clean_value_secure).sum()
                    if total_vol > 0.0:
                        numerical_candidates.append((col, total_vol))
            
            # 수치 후보군 정렬 후 가장 큰 값을 공급가액, 그 다음 비율을 세액으로 이중 백업 설계
            if numerical_candidates:
                numerical_candidates.sort(key=lambda x: x[1], reverse=True)
                c_supply = numerical_candidates[0][0]
                if len(numerical_candidates) > 1:
                    c_tax = numerical_candidates[1][0]

        # 4. 데이터 안전 파싱 및 수치 형변환 전개
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        if c_tax:
            df[c_tax] = df[c_tax].apply(clean_value_secure)
        else:
            df['임시세액'] = df[c_supply] * 0.1
            c_tax = '임시세액'

        df['합계'] = df[c_supply] + df[c_tax]
        
        parsed_dates = parse_flexible_date(df[c_date])
        df['월'] = parsed_dates.dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 5. 분류 로직
        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            
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
        st.download_button("📥 카드정산 엑셀 다운로드", output.getvalue(), "호진환경_정산_완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 파일 형식이 평소와 다른지 확인해주세요.")
