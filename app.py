import os
import requests
from flask import Flask, render_template, jsonify, request
import re
import time
from datetime import datetime
import pandas as pd
from io import StringIO
import yfinance as yf
import xml.etree.ElementTree as ET

app = Flask(__name__)

# 전역 변수 설정
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')
stock_cache = {}

# --- [1. 종목 사전 업데이트 (네이버 금융 기반)] ---
def update_stock_dictionary():
    print("🚀 실시간 종목 리스트 수집 시작...")
    stock_dict = {"삼성전자": "005930", "SK하이닉스": "000660", "카카오": "035720"}
    try:
        for sosok in [0, 1]: 
            for page in range(1, 11): 
                url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                df = pd.read_html(StringIO(res.text), encoding='cp949')[1].dropna(subset=['종목명'])
                for _, row in df.iterrows():
                    name = str(row['종목명']).strip()
                    if name: stock_dict[name] = "SEARCH"
        print(f"✅ 총 {len(stock_dict)}개 종목 확보 성공!")
        return stock_dict
    except:
        return stock_dict

STOCK_MASTER = update_stock_dictionary()
STOCK_NAMES = list(STOCK_MASTER.keys())

# --- [2. 시간 정렬을 위한 파서] ---
def parse_date_to_ts(date_str):
    """네이버/구글의 다양한 날짜 형식을 비교 가능한 숫자로 변환"""
    formats = [
        '%a, %d %b %Y %H:%M:%S %Z',    # Google (GMT)
        '%a, %d %b %Y %H:%M:%S +0900', # Naver (KST)
        '%Y-%m-%d %H:%M:%S'            # Fallback
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).timestamp()
        except: continue
    return 0

# --- [3. 기능 함수] ---
def get_stock_price(stock_name):
    code = STOCK_MASTER.get(stock_name)
    if not code or code == "SEARCH": return None
    for suffix in [".KS", ".KQ"]:
        try:
            ticker = yf.Ticker(f"{code}{suffix}")
            hist = ticker.history(period="2d")
            if not hist.empty:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                return {"price": f"{int(curr):,}", "change": round(((curr-prev)/prev)*100, 2)}
        except: continue
    return None

def get_google_news(query):
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url)
        root = ET.fromstring(res.text)
        return [{"title": item.find('title').text, "link": item.find('link').text, 
                 "pubDate": item.find('pubDate').text, "source": "Google"} 
                for item in root.findall('.//item')[:10]]
    except: return []

# --- [4. 라우팅] ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_top_stocks')
def get_top_stocks():
    theme = request.args.get('theme', '반도체')
    url = f"https://openapi.naver.com/v1/search/news.json?query={theme}&display=100&sort=date"
    headers = {"X-Naver-Client-Id": SEARCH_ID, "X-Naver-Client-Secret": SEARCH_SECRET}
    try:
        res = requests.get(url, headers=headers).json().get('items', [])
        content = " ".join([i['title'] for i in res])
        counts = [{"name": n, "count": content.count(n)} for n in STOCK_NAMES if n in content]
        top5 = sorted(counts, key=lambda x: x['count'], reverse=True)[:5]
        if top5:
            stock_cache[theme] = {"data": top5, "time": datetime.now().strftime('%H:%M:%S')}
        return jsonify(top5)
    except: return jsonify([])

@app.route('/get_stock_info')
def get_stock_info():
    stock = request.args.get('stock')
    headers = {"X-Naver-Client-Id": SEARCH_ID, "X-Naver-Client-Secret": SEARCH_SECRET}
    n_url = f"https://openapi.naver.com/v1/search/news.json?query={stock}&display=30&sort=date"
    n_res = requests.get(n_url, headers=headers).json().get('items', [])
    
    naver_news = [{"title": re.sub('<[^>]*>', '', i['title']), "link": i['link'], 
                   "pubDate": i['pubDate'], "ts": parse_date_to_ts(i['pubDate']), "source": "Naver"} for i in n_res]
    google_news = [{"title": i['title'], "link": i['link'], "pubDate": i['pubDate'], 
                    "ts": parse_date_to_ts(i['pubDate']), "source": "Google"} for i in get_google_news(stock)]
    
    # 통합 정렬 (최신순)
    combined = sorted(naver_news + google_news, key=lambda x: x['ts'], reverse=True)
    return jsonify({"price_info": get_stock_price(stock), "news": combined})

@app.route('/get_all_top_stocks')
def get_all_top_stocks():
    all_counts = {}
    last_time = "업데이트 중..."
    for t in stock_cache:
        last_time = stock_cache[t]['time']
        for item in stock_cache[t]['data']:
            name = item['name']
            all_counts[name] = max(all_counts.get(name, 0), item['count'])
    
    sorted_all = sorted([{"name": k, "count": v} for k, v in all_counts.items()], 
                        key=lambda x: x['count'], reverse=True)[:5]
    return jsonify({"stocks": sorted_all, "update_time": last_time})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)