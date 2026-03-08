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

app = Flask(__name__)

SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

# --- [1. 종목 사전 및 티커 매핑] ---
def update_stock_dictionary():
    print("🚀 KRX 상장사 명단을 가져오는 중...")
    try:
        # KIND의 엑셀 다운로드 URL
        url = "https://kind.or.kr/corpgeneral/corpList.do?method=download"
        
        # [핵심] 브라우저인 척 속이는 헤더 정보 추가
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://kind.or.kr/corpgeneral/corpList.do?method=main'
        }
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 데이터를 가져올 때 headers를 꼭 포함합니다.
        res = requests.get(url, verify=False, headers=headers, timeout=15)
        res.encoding = 'cp949'
        
        # [중요] lxml 엔진을 직접 명시하여 HTML 표를 찾게 합니다.
        # pandas 2.0 이상에서는 여기서 'No tables found'가 자주 나는데, 
        # StringIO나 BytesIO 처리를 명확히 해줍니다.
        from io import StringIO
        html_content = res.text
        
        # 표가 있는지 먼저 확인 후 파싱
        if '<table>' not in html_content.lower():
            print("⚠️ 표를 찾지 못했습니다. 원본 텍스트 일부:", html_content[:100])
            raise ValueError("HTML에 table 태그가 없습니다.")

        df = pd.read_html(StringIO(html_content))[0]
        
        # 종목코드 6자리 포맷팅
        df['종목코드'] = df['종목코드'].apply(lambda x: f"{x:06d}")
        stock_dict = df.set_index('회사명')['종목코드'].to_dict()
        
        print(f"✅ 총 {len(stock_dict)}개 종목 로드 완료")
        return stock_dict
        
    except Exception as e:
        print(f"❌ 사전 업데이트 실패: {e}")
        # 실패 시 수익화 서비스를 중단시키지 않기 위한 최소한의 데이터
        return {"삼성전자": "005930", "SK하이닉스": "000660", "네이버": "035420", "에코프로": "086520"}
        
STOCK_MASTER = update_stock_dictionary()
STOCK_NAMES = list(STOCK_MASTER.keys())

# --- [2. 주가 정보 가져오기] ---
def get_stock_price(stock_name):
    code = STOCK_MASTER.get(stock_name)
    if not code: return None
    
    # 한국 주식은 .KS(코스피) 또는 .KQ(코스닥) 접미사가 필요함
    # 여기서는 간단히 두 곳 다 시도하거나 기본 처리
    ticker_symbol = f"{code}.KS" 
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 코스피(.KS)에서 먼저 찾아보고 데이터가 없으면 코스닥(.KQ)으로 재시도
        ticker = yf.Ticker(f"{code}.KS")
        if ticker.fast_info.last_price is None:
            ticker = yf.Ticker(f"{code}.KQ")
        data = ticker.fast_info
        current_price = data.last_price
        prev_close = data.previous_close
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