import streamlit as st
import pandas as pd
import numpy as np
import io

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.0 완벽 정비판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.0)")
st.caption("3개월 만의 구동 시 발생하는 수치형 0값 수렴 버그를 원천 제거하고, 유연한 한글 날짜 및 금액 전처리 필터를 가동합니다.")

# 작업 선택
job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구] 문자열 금액 및 유연한 날짜 변환기
# ==========================================
def parse_clean_money(series):
    """금액 시리즈 내 쉼표, 원화, 공백, 따옴표를 완전 소독하여 완벽한 정수/실수형으로 강제 매핑합니다."""
    # 문자로 변환 후 원화 기호, 콤마, 따옴표, 공백을 물리적으로 박멸
    cleaned = series.astype(str).str.replace(',', '').str.replace('원', '').str.replace('"', '').str.strip()
    # 숫자가 아닌 빈값이나 불량 텍스트는 0으로 치환 후 부동 소수점 변환
    return pd.to_numeric(cleaned, errors='coerce').fillna(0)

def parse_flexible_date(series):
    """한글 날짜('2017년01월01일') 및 기호 날짜 형식을 완벽한 표준 datetime으로 번역합니다."""
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    # 한글 년, 월, 일 문장 제거 매핑
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
        for i in range(min(len(df_raw), 25)): # 상위 25줄 이내에서 세밀 탐색
            row_vals = df_raw.iloc[i].fillna('').values
            row_str = "".join(map(str, row_vals)).replace(" ", "")
            # 매입/매출/카드 헤더 키워드 교차 검증
            if any(k in row_str for k in ['일자', '공급가액', '승인번호', '거래처', '상호', '세액']):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 🚨 [컬럼 정규화] 열 이름의 양끝 공백을 완전히 제거하여 판다스가 인식하지 못하는 현상을 선제 방어합니다.
        df.columns = [str(c).strip() for c in df.columns]

        # 3. 🔍 기둥 매칭 (카드 및 세금계산서 양식 유연성 가드레일 수립)
        # 일자 기둥 검색
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['일자', '일시', '작성일'])), df.columns[0])
        
        # 상호명 기둥 (가맹점명 등)
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '가맹점', '거래처', '회사명', '공급자'])), None)
        if not c_name:
            c_name = df.columns[3] if len(df.columns) > 3 else df.columns[1]
            
        # 금액 기둥 (공급가액, 세액)
        c_supply = next((c for c in df.columns if any(k in str(c) for k in ['공급가액', '공급가'])), None)
        if not c_supply: 
            c_supply = next((c for c in df.columns if any(k in str(c) for k in ['금액', '합계', '승인금액', '이용금액'])), df.columns[-1])
            
        c_tax = next((c for c in df.columns if any(k in str(c) for k in ['세액', '부가세'])), None)

        # 🚨 [수리 완료] 정밀 수치 정세 소독 필터링 대입
        df[c_supply] = parse_clean_money(df[c_supply])
        if c_tax:
            df[c_tax] = parse_clean_money(df[c_tax])
        else:
            # 세액 컬럼이 별도로 발견되지 않는 경우 공급가액의 10%를 역산하여 메웁니다.
            df['임시세액'] = df[c_supply] * 0.1 / 1.1 
            c_tax = '임시세액'

        df['합계'] = df[c_supply] + df[c_tax]
        
        # 날짜 타입 보정 및 월 데이터 계산 바인딩
        parsed_dates = parse_flexible_date(df[c_date])
        df['월'] = parsed_dates.dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 4. 분류 로직
        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            name_val = str(row[c_name]).replace(" ", "").lower()
            
            # [조건 1] 남상민 건 (줄 전체 검색)
            if '남상민' in full_text:
                ansan_list.append(row)
            # [조건 2] 성남/수정/경찰서 (안산 본점 분류)
            elif any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append(row)
            # [조건 3] 그 외의 거래처는 인천 지점으로 안전하게 분류
            else:
                incheon_list.append(row)

        # 5. 결과 정리 및 소계/총계 연산 엔진
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
            # '월' 데이터를 안전하게 일치시켜 그룹화 연산
            temp_dates = parse_flexible_date(display_df['작성일자'])
            display_df['temp_month'] = temp_dates.dt.month.fillna(0).astype(int)
            
            for month, group in display_df.groupby('temp_month'):
                # 불필요한 임시 매핑 칼럼 제거
                group_clean = group.drop(columns=['temp_month'])
                final_rows.append(group_clean)
                
                # 소계 기입
                sub = pd.DataFrame([{
                    '작성일자': f"{int(month)}월 소계", 
                    '상호': "", 
                    '공급가액': group['공급가액'].sum(), 
                    '세액': group['세액'].sum(), 
                    '합계': group['합계'].sum()
                }])
                final_rows.append(sub)
            
            # 총 계 기입
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

        # 6. 다운로드 및 표시
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
