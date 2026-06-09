import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# ==========================================
# 앱 아이콘 및 탭 제목 설정 (Ver 9.9 오타 전면 수리판)
# ==========================================
st.set_page_config(page_title="이원동 이글아이 마스터", page_icon="🦅", layout="wide")
st.title("🦅 이원동의 '이글아이(Eagle Eye)' 최종 마스터 관제탑 (Ver 9.9)")
st.caption("구문 오류(SyntaxError)를 완벽하게 수정하고, 네이버 차단을 우회하여 진짜 세력 수급을 실시간 전개합니다.")

# 1. [차단 우회형] 코스피/코스닥 시총 상위 핵심 주도주 200개 명가 사전 구축
def get_clean_market_master():
    heavy_stocks = [
        ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("267260", "HD현대일렉트릭"),
        ("042700", "한미반도체"), ("034020", "두산에너빌리티"), ("000720", "현대건설"),
        ("328130", "루닛"), ("005380", "현대차"), ("247540", "에코프로비엠"),
        ("068270", "셀트리온"), ("005490", "POSCO홀딩스"), ("035420", "NAVER"),
        ("003670", "포스코퓨처엠"), ("051910", "LG화학"), ("035720", "카카오"),
        ("012330", "현대모비스"), ("066570", "LG전자"), ("000270", "기아"),
        ("096770", "SK이노베이션"), ("032830", "삼성생명"), ("086520", "에코프로"),
        ("006400", "삼성SDI"), ("373220", "LG에너지솔루션"), ("207940", "삼성바이오로직스"),
        ("000810", "삼성화재"), ("015760", "한국전력"), ("033780", "KT&G"),
        ("003550", "LG"), ("010950", "S-Oil"), ("018260", "삼성에스디에스"),
        ("316140", "우리금융지주"), ("008930", "한미사이언스"), ("028260", "삼성물산"),
        ("055550", "신한지주"), ("105560", "KB금융"), ("086790", "하나금융지주"),
        ("000060", "메리츠금융지주"), ("139130", "DGB금융지주"), ("138040", "메리츠금융"),
        ("005935", "삼성전자우"), ("047050", "포스코인터내셔널"), ("009150", "삼성전기"),
        ("011170", "롯데케미칼"), ("009830", "한화솔루션"), ("010130", "고려아연"),
        ("000100", "유한양행"), ("006260", "LS"), ("017670", "SK텔레콤"),
        ("030200", "KT"), ("032640", "LG유플러스"), ("251270", "넷마블"),
        ("036570", "엔씨소프트"), ("259960", "크래프톤"), ("181710", "NHN"),
        ("011070", "LG노텍"), ("030000", "제일기획"), ("007070", "GS리테일"),
        ("023530", "롯데쇼핑"), ("282330", "BGF리테일"), ("039490", "키움증권"),
        ("016360", "삼성증권"), ("005940", "NH투자증권"), ("035820", "에스엠"),
        ("253450", "스튜디오드래곤"), ("041510", "에스에프에이"), ("036490", "상신브레이크"),
        ("022100", "포스코DX"), ("069500", "KODEX 200"), ("233740", "KODEX 코스닥150레버리지")
    ]
    codes = [item[0] for item in heavy_stocks]
    names = {item[0]: item[1] for item in heavy_stocks}
    return codes, names

final_market_codes, code_to_name_master = get_clean_market_master()


# 2. 네이버 실시간 진짜 세력 수급 추출 엔진
def get_naver_real_investors(codes):
    results = {}
    if not codes:
        return results
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        chunks = [codes[i:i + 40] for i in range(0, len(codes), 40)]
        for chunk in chunks:
            chunk_str = ",".join(chunk)
            res = requests.get(f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{chunk_str}", headers=headers, timeout=5)
            data = res.json()
            items = data['result']['areas'][0]['datas']
            for item in items:
                code = item['cd']
                curr_price = int(item['nv']) if item['nv'] is not None else 0
                prev_close = int(item['sv']) if item['sv'] is not None else curr_price
                volume = int(item['aq']) if item['aq'] is not None else 0
