import os
import requests
from flask import Flask, render_template, jsonify, request
import re
import time
import pandas as pd
from io import BytesIO
import yfinance as yf
import xml.etree.ElementTree as ET
import ssl # 상단에 추가
import FinanceDataReader as fdr  # 추가

app = Flask(__name__)

SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

def update_stock_dictionary():
    print("🚀 종목 사전 동적 업데이트 시작...")
    
    # [1단계] 내장 기본 사전 (절대 죽지 않는 0순위 백업)
    stock_master = {"삼성전자": "005930", "SK하이닉스": "000660", "에코프로": "086520"} 

    # [2단계] Naver 금융 또는 GitHub에 저장된 최신 종목 리스트 가져오기
    # KIND가 막혔을 때 가장 안정적인 대체 소스는 네이버 금융의 시총 상위 페이지입니다.
    try:
        print("🔍 네이버 금융에서 실시간 상위 종목 수집 중...")
        # 시가총액 상위 200개 정도만 가져와도 웬만한 핫토픽은 다 잡힙니다.
        for page in range(1, 5): # 1~4페이지 (총 200개)
            url = f"https://finance.naver.com/sise/sise_market_sum.naver?&page={page}"
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            df = pd.read_html(StringIO(res.text), encoding='cp949')[1]
            df = df.dropna(subset=['종목명'])
            
            for _, row in df.iterrows():
                name = str(row['종목명'])
                # 종목코드는 href 링크 안에 숨어있으므로 여기서 추출하거나 
                # yfinance가 찾을 수 있게 이름만이라도 저장
                stock_master[name] = "SEARCH" # 코드를 모를 땐 이름만 저장 후 나중에 검색
        
        print(f"✅ 실시간 종목 포함 총 {len(stock_master)}개 로드 완료")
        return stock_master

    except Exception as e:
        print(f"⚠️ 실시간 수집 실패({e}), 내장 사전을 확장하여 사용합니다.")
        # 실패 시 제가 미리 준비한 '광범위 리스트(200개)'를 더해줍니다.
        stock_master.update(get_backup_list()) 
        return stock_master

def get_backup_list():
    # 여기에 거래량 상위 200~300개 리스트를 텍스트로 박아둡니다.
    return {"삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380", "LG에너지솔루션": "373220",
        "삼성바이오로직스": "207940", "기아": "000270", "셀트리온": "068270", "POSCO홀딩스": "005490",
        "KB금융": "105560", "네이버": "035420", "NAVER": "035420", "신한지주": "055550",
        "삼성물산": "028260", "현대모비스": "012330", "포스코퓨처엠": "003670", "카카오": "035720",
        "삼성 SDI": "006400", "LG화학": "051910", "HMM": "011200", "에코프로": "086520",
        "에코프로비엠": "247540", "알테오젠": "196170", "HLB": "028300", "엔켐": "348370",
        "한미반도체": "042700", "신성델타테크": "065350", "제주반도체": "080220", "두산로보틱스": "454910",
        "LS 에코에너지": "229640", "대한항공": "003490", "아시아나항공": "020560", "한화에어로스페이스": "012450",
        "LIG넥스원": "079550", "현대로템": "064350", "SK이노베이션": "096770", "S-Oil": "010950"} # (생략)

STOCK_MASTER = update_stock_dictionary()
STOCK_NAMES = list(STOCK_MASTER.keys())

# --- [2. 주가 정보 및 뉴스 로직 (기존과 동일)] ---
def get_stock_price(stock_name):
    code = STOCK_MASTER.get(stock_name)
    if not code: return None
    
    # 한국 주식 티커 설정
    ticker_symbol = f"{code}.KS" 
    try:
        ticker = yf.Ticker(ticker_symbol)
        # .fast_info가 가끔 에러날 수 있어 .history로 보완
        hist = ticker.history(period="2d")
        if hist.empty:
            ticker_symbol = f"{code}.KQ" # 코스닥 재시도
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="2d")
            
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        return {
            "price": f"{int(current_price):,}",
            "change": round(change_pct, 2),
            "symbol": ticker_symbol
        }
    except:
        return None

# --- [3. 구글 뉴스 확장 (RSS)] ---
def get_google_news(query):
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url)
        root = ET.fromstring(res.text)
        news_items = []
        for item in root.findall('.//item')[:10]: # 상위 10개만
            news_items.append({
                "title": item.find('title').text,
                "link": item.find('link').text,
                "pubDate": item.find('pubDate').text,
                "source": "Google"
            })
        return news_items
    except:
        return []

# --- [4. 라우팅] ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_top_stocks')
def get_top_stocks():
    theme = request.args.get('theme', '반도체')
    url = f"https://openapi.naver.com/v1/search/news.json?query={theme}&display=100&sort=sim"
    headers = {"X-Naver-Client-Id": SEARCH_ID, "X-Naver-Client-Secret": SEARCH_SECRET}
    
    try:
        res = requests.get(url, headers=headers)
        items = res.json().get('items', [])
        all_content = " ".join([i['title'] for i in items])
        
        counts = []
        for name in STOCK_NAMES:
            if name in all_content:
                counts.append({"name": name, "count": all_content.count(name)})
        
        top5 = sorted(counts, key=lambda x: x['count'], reverse=True)[:5]
        return jsonify(top5)
    except:
        return jsonify([])

@app.route('/get_stock_info')
def get_stock_info():
    stock = request.args.get('stock')
    price_data = get_stock_price(stock)
    
    # 네이버 뉴스
    headers = {"X-Naver-Client-Id": SEARCH_ID, "X-Naver-Client-Secret": SEARCH_SECRET}
    n_url = f"https://openapi.naver.com/v1/search/news.json?query={stock}&display=20&sort=date"
    n_res = requests.get(n_url, headers=headers).json().get('items', [])
    naver_news = [{"title": re.sub('<[^>]*>', '', i['title']), "link": i['link'], "pubDate": i['pubDate'], "source": "Naver"} for i in n_res]
    
    # 구글 뉴스 통합
    google_news = get_google_news(stock)
    combined_news = sorted(naver_news + google_news, key=lambda x: x['pubDate'], reverse=True)
    
    return jsonify({
        "price_info": price_data,
        "news": combined_news
    })

    @app.route('/get_all_top_stocks')
def get_all_top_stocks():
    # 모든 테마에서 수집된 종목 중 가장 많이 언급된 통합 TOP 5 추출
    # (이미 stock_cache에 데이터가 쌓여있어야 작동합니다)
    all_counts = {}
    for theme in stock_cache:
        for item in stock_cache[theme]['data']:
            name = item['name']
            all_counts[name] = max(all_counts.get(name, 0), item['count'])
    
    sorted_all = sorted([{"name": k, "count": v} for k, v in all_counts.items()], 
                        key=lambda x: x['count'], reverse=True)[:5]
    
    # 데이터가 아직 없으면 기본값 반환
    if not sorted_all:
        return jsonify([{"name": "데이터 수집 중", "count": 0}])
        
    return jsonify(sorted_all)@app.route('/get_all_top_stocks')
def get_all_top_stocks():
    # 모든 테마에서 수집된 종목 중 가장 많이 언급된 통합 TOP 5 추출
    # (이미 stock_cache에 데이터가 쌓여있어야 작동합니다)
    all_counts = {}
    for theme in stock_cache:
        for item in stock_cache[theme]['data']:
            name = item['name']
            all_counts[name] = max(all_counts.get(name, 0), item['count'])
    
    sorted_all = sorted([{"name": k, "count": v} for k, v in all_counts.items()], 
                        key=lambda x: x['count'], reverse=True)[:5]
    
    # 데이터가 아직 없으면 기본값 반환
    if not sorted_all:
        return jsonify([{"name": "데이터 수집 중", "count": 0}])
        
    return jsonify(sorted_all)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)