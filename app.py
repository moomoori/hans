import os
import requests
from flask import Flask, render_template, jsonify, request
from datetime import datetime
import re
import time

app = Flask(__name__)

# 환경변수 (Render 설정 필요)
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

# 테마별 종목 리스트
THEME_STOCKS = {
    "반도체": ["삼성전자", "SK하이닉스", "한미반도체", "DB하이텍", "리노공업", "HPSP"],
    "2차전지": ["LG에너지솔루션", "삼성SDI", "에코프로", "포스코홀딩스", "엘앤에프", "금양"],
    "AI/로봇": ["네이버", "카카오", "레인보우로보틱스", "두산로보틱스", "셀바스AI", "이스트소프트"],
    "바이오": ["삼성바이오로직스", "셀트리온", "유한양행", "HLB", "알테오젠", "SK바이오팜"]
}

# --- 캐싱을 위한 전역 변수 ---
stock_cache = {}  # { '반도체': {'data': [...], 'time': 12345678} }
news_cache = {}   # { '삼성전자': {'data': [...], 'time': 12345678} }
CACHE_EXPIRE = 600  # 10분 (600초)

def get_headers():
    return {
        "X-Naver-Client-Id": SEARCH_ID,
        "X-Naver-Client-Secret": SEARCH_SECRET
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_top_stocks')
def get_top_stocks():
    theme = request.args.get('theme', '반도체')
    now = time.time()

    # 10분 이내의 캐시가 있다면 즉시 반환
    if theme in stock_cache and (now - stock_cache[theme]['time'] < CACHE_EXPIRE):
        return jsonify(stock_cache[theme]['data'])

    # 캐시가 없거나 만료되었다면 API 호출
    stocks = THEME_STOCKS.get(theme, [])
    url = f"https://openapi.naver.com/v1/search/news.json?query={theme} 주식&display=100&sort=date"
    
    try:
        res = requests.get(url, headers=get_headers())
        items = res.json().get('items', [])
        all_titles = " ".join([item['title'] for item in items])
        
        counts = []
        for s in stocks:
            count = all_titles.count(s)
            if count > 0:
                counts.append({"name": s, "count": count})
        
        top5 = sorted(counts, key=lambda x: x['count'], reverse=True)[:5]
        
        # 결과 캐싱
        stock_cache[theme] = {'data': top5, 'time': now}
        return jsonify(top5)
    except:
        return jsonify([])

@app.route('/get_stock_news')
def get_stock_news():
    stock = request.args.get('stock')
    now = time.time()

    # 뉴스 데이터 캐싱 확인
    if stock in news_cache and (now - news_cache[stock]['time'] < CACHE_EXPIRE):
        return jsonify(news_cache[stock]['data'])

    url = f"https://openapi.naver.com/v1/search/news.json?query={stock}&display=20&sort=date"
    
    try:
        res = requests.get(url, headers=get_headers())
        items = res.json().get('items', [])
        
        results = []
        for item in items:
            clean_title = re.sub('<[^>]*>', '', item['title'])
            link = item['originallink'] if item['originallink'] else item['link']
            results.append({
                "title": clean_title,
                "link": link,
                "pubDate": item['pubDate']
            })
        
        # 결과 캐싱
        news_cache[stock] = {'data': results, 'time': now}
        return jsonify(results)
    except:
        return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)