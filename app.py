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

# --- [1. 종목 사전 및 티커 매핑] ---
# --- [1. 종목 사전 자동 업데이트 - FinanceDataReader 활용] ---
def update_stock_dictionary():
    print("🚀 FinanceDataReader를 통해 종목 명단을 가져오는 중...")
    try:
        # KRX(코스피, 코스닥, 코넥스) 전체 종목 리스트를 가져옵니다.
        df = fdr.StockListing('KRX')
        
        # 종목명과 종목코드를 매핑 (Code 컬럼 사용)
        # FinanceDataReader는 코드를 문자열로 예쁘게 가져와줍니다.
        stock_dict = df.set_index('Name')['Code'].to_dict()
        
        print(f"✅ 총 {len(stock_dict)}개 종목 로드 완료 (FDR 방식)")
        return stock_dict
    except Exception as e:
        print(f"❌ FDR 로드 실패: {e}. 내장 사전으로 전환합니다.")
        return {"삼성전자": "005930", "SK하이닉스": "000660", "현대차": "005380"}

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)