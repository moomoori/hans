import os
import requests
from flask import Flask, render_template, jsonify, request
import re
import time
import random
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
        counts_dict = {name: 0 for name in STOCK_NAMES}
        
        for item in res:
            content = (item['title'] + item['description']).replace('<b>', '').replace('</b>', '')
            for name in STOCK_NAMES:
                if name in content:
                    counts_dict[name] += 1
        
        top5 = []
        for name, count in counts_dict.items():
            if count > 0:
                top5.append({"name": name, "count": count})
        
        top5 = sorted(top5, key=lambda x: x['count'], reverse=True)[:5]
        
        if top5:
            stock_cache[theme] = {"data": top5, "time": datetime.now().strftime('%H:%M:%S')}
            
        return jsonify(top5)
    except Exception as e:
        print(f"❌ 오류: {e}")
        return jsonify([])

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

# --- [추가된 데일리 리포트 기능] ---
@app.route('/get_daily_report')
def get_daily_report():
    if not stock_cache:
        return jsonify({"report": "실시간 시장 트렌드를 분석 중입니다. 데이터를 수집할 때까지 잠시만 기다려 주세요."})
    
    all_items = []
    for theme in stock_cache:
        for item in stock_cache[theme]['data']:
            all_items.append(item)
    
    if not all_items:
        return jsonify({"report": "분석할 데이터가 부족합니다. 종목 탭을 클릭해 보세요!"})

    # 가장 언급량이 많은 종목 추출
    top_stock = sorted(all_items, key=lambda x: x['count'], reverse=True)[0]
    
    templates = [
        f"오늘 투자자들은 '{top_stock['name']}'에 가장 주목하고 있습니다. 뉴스 요약문 기준 {top_stock['count']}건의 기사에서 언급되었습니다.",
        f"현재 시장의 가장 뜨거운 키워드는 '{top_stock['name']}'입니다. 관련 소식들이 실시간으로 쏟아지는 중입니다.",
        f"오늘의 핫 토픽! '{top_stock['name']}' 관련 기사가 전체 테마 중 압도적인 빈도를 기록하며 트렌드를 주도하고 있습니다."
    ]
    
    return jsonify({
        "report": random.choice(templates),
        "time": datetime.now().strftime('%Y-%m-%d %H:%M')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)