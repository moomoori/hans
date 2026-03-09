import os
import requests
from flask import Flask, render_template, jsonify, request
import re
import time
import pandas as pd
from io import BytesIO, StringIO
import yfinance as yf
import xml.etree.ElementTree as ET
import ssl

app = Flask(__name__)

# 전역 변수 설정
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')
stock_cache = {}  # TOP 5 데이터를 임시 저장할 공간

# --- [1. 종목 사전 업데이트 로직] ---
def update_stock_dictionary():
    print("🚀 네이버 금융에서 실시간 종목 리스트 수집 시작...")
    stock_dict = {"삼성전자": "005930", "SK하이닉스": "000660", "카카오": "035720"}
    
    try:
        for sosok in [0, 1]: 
            for page in range(1, 11): # 속도를 위해 우선 10페이지까지 수집 (500개)
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                df_list = pd.read_html(StringIO(res.text), encoding='cp949')
                df = df_list[1].dropna(subset=['종목명'])
                
                for _, row in df.iterrows():
                    name = str(row['종목명']).strip()
                    if name:
                        stock_dict[name] = "SEARCH" 
        
        print(f"✅ 총 {len(stock_dict)}개 종목 명단 확보 성공!")
        return stock_dict
    except Exception as e:
        print(f"⚠️ 네이버 수집 중 오류({e}), 기본 사전을 반환합니다.")
        return stock_dict

STOCK_MASTER = update_stock_dictionary()
STOCK_NAMES = list(STOCK_MASTER.keys())

# --- [2. 기능 함수들] ---
def get_stock_price(stock_name):
    code = STOCK_MASTER.get(stock_name)
    if not code or code == "SEARCH": return None
    
    ticker_symbol = f"{code}.KS" 
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d")
        if hist.empty:
            ticker_symbol = f"{code}.KQ"
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

def get_google_news(query):
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url)
        root = ET.fromstring(res.text)
        news_items = []
        for item in root.findall('.//item')[:10]:
            news_items.append({
                "title": item.find('title').text,
                "link": item.find('link').text,
                "pubDate": item.find('pubDate').text,
                "source": "Google"
            })
        return news_items
    except:
        return []

# --- [3. 라우팅 로직] ---

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
        
        # 통합 순위를 위해 캐시에 저장
        if top5:
            stock_cache[theme] = {"data": top5, "time": time.time()}
            
        return jsonify(top5)
    except:
        return jsonify([])

@app.route('/get_stock_info')
def get_stock_info():
    stock = request.args.get('stock')
    price_data = get_stock_price(stock)
    
    headers = {"X-Naver-Client-Id": SEARCH_ID, "X-Naver-Client-Secret": SEARCH_SECRET}
    n_url = f"https://openapi.naver.com/v1/search/news.json?query={stock}&display=20&sort=date"
    n_res = requests.get(n_url, headers=headers).json().get('items', [])
    naver_news = [{"title": re.sub('<[^>]*>', '', i['title']), "link": i['link'], "pubDate": i['pubDate'], "source": "Naver"} for i in n_res]
    
    google_news = get_google_news(stock)
    combined_news = sorted(naver_news + google_news, key=lambda x: x['pubDate'], reverse=True)
    
    return jsonify({
        "price_info": price_data,
        "news": combined_news
    })

@app.route('/get_all_top_stocks')
def get_all_top_stocks():
    all_counts = {}
    for theme in stock_cache:
        for item in stock_cache[theme]['data']:
            name = item['name']
            all_counts[name] = max(all_counts.get(name, 0), item['count'])
    
    sorted_all = sorted([{"name": k, "count": v} for k, v in all_counts.items()], 
                        key=lambda x: x['count'], reverse=True)[:5]
    
    if not sorted_all:
        return jsonify([{"name": "데이터 수집 중", "count": 0}])
        
    return jsonify(sorted_all)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)