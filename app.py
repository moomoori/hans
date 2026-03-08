import os
import requests
from flask import Flask, render_template, jsonify, request
import re
import time
import pandas as pd
from io import BytesIO

app = Flask(__name__)

# 환경변수 (Render 설정: NAVER_SEARCH_ID, NAVER_SEARCH_SECRET)
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

# --- [1. 종목 사전 자동 업데이트 로직] ---
def update_stock_dictionary():
    """한국거래소(KRX) 상장법인 목록을 가져와 종목 사전 생성"""
    print("🚀 종목 사전을 최신 상태로 업데이트 중...")
    try:
        # KIND 상장법인 목록 다운로드 URL (가장 가볍고 정확함)
        url = "https://kind.or.kr/corpgeneral/corpList.do?method=download"
        res = requests.get(url)
        
        # HTML 표 형식의 데이터를 pandas로 읽기
        df = pd.read_html(BytesIO(res.content), header=0)[0]
        
        # '회사명' 컬럼만 추출하여 리스트화
        stock_list = df['회사명'].tolist()
        
        # 2글자 미만 또는 너무 일반적인 단어 제외 (필터링)
        # 예: '기아', '현대' 등은 오탐지가 잦을 수 있으나 종목명 그대로 유지
        stock_list = [s for s in stock_list if len(str(s)) >= 2]
        
        print(f"✅ 총 {len(stock_list)}개의 종목이 사전에 등록되었습니다.")
        return list(set(stock_list))
    except Exception as e:
        print(f"❌ 사전 업데이트 실패: {e}")
        # 실패 시 최소한의 우량주 리스트로 대체
        return ["삼성전자", "SK하이닉스", "LG에너지솔루션", "현대차", "셀트리온", "네이버", "카카오"]

# 서버 시작 시 종목 사전 로드
STOCK_DICTIONARY = update_stock_dictionary()

# --- [2. 캐싱 및 헬퍼 함수] ---
stock_cache = {}
news_cache = {}
CACHE_EXPIRE = 600  # 10분

def get_headers():
    return {
        "X-Naver-Client-Id": SEARCH_ID,
        "X-Naver-Client-Secret": SEARCH_SECRET
    }

def clean_html(text):
    if not text: return ""
    clean = re.sub('<[^>]*>', '', text)
    clean = clean.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')
    return clean

# --- [3. 웹 라우팅] ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_top_stocks')
def get_top_stocks():
    theme = request.args.get('theme', '반도체')
    now = time.time()

    if theme in stock_cache and (now - stock_cache[theme]['time'] < CACHE_EXPIRE):
        return jsonify(stock_cache[theme]['data'])

    # 뉴스 수집 (관련도순 100개)
    url = f"https://openapi.naver.com/v1/search/news.json?query={theme}&display=100&sort=sim"
    
    try:
        res = requests.get(url, headers=get_headers())
        items = res.json().get('items', [])
        
        # 제목 + 요약글 통합 텍스트
        all_content = " ".join([clean_html(item['title'] + " " + item['description']) for item in items])
        
        # 종목 사전과 매칭 (성능을 위해 텍스트에 포함된 것만 카운트)
        counts = []
        for s in STOCK_DICTIONARY:
            if s in all_content:
                count = all_content.count(s)
                counts.append({"name": s, "count": count})
        
        # 많이 언급된 순 정렬
        top5 = sorted(counts, key=lambda x: x['count'], reverse=True)[:5]
        
        if not top5:
            top5 = [{"name": f"{theme} 관련주 분석 중", "count": 0}]

        stock_cache[theme] = {'data': top5, 'time': now}
        return jsonify(top5)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify([])

@app.route('/get_stock_news')
def get_stock_news():
    stock = request.args.get('stock')
    now = time.time()

    if stock in news_cache and (now - news_cache[stock]['time'] < CACHE_EXPIRE):
        return jsonify(news_cache[stock]['data'])

    url = f"https://openapi.naver.com/v1/search/news.json?query={stock}&display=20&sort=date"
    
    try:
        res = requests.get(url, headers=get_headers())
        items = res.json().get('items', [])
        
        results = []
        for item in items:
            results.append({
                "title": clean_html(item['title']),
                "link": item.get('originallink') or item.get('link'),
                "pubDate": item['pubDate']
            })
        
        news_cache[stock] = {'data': results, 'time': now}
        return jsonify(results)
    except Exception as e:
        return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)