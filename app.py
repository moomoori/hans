import os
import random
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Render 환경변수 설정 (네이버 클라우드에서 발급받은 키)
CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

@app.route('/')
def index():
    return render_template('index.html', client_id=CLIENT_ID)

@app.route('/recommend_v2')
def recommend_v2():
    location = request.args.get('location', '서울 강남역')
    food = request.args.get('food', '맛집')
    query = f"{location} {food}"
    
    # 검색 API 호출 (리뷰 순 정렬 시도)
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=10&sort=comment"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        if data.get('items'):
            # 상위 5개 결과 추출
            items = data['items'][:5]
            results = []
            for item in items:
                results.append({
                    "name": item['title'].replace('<b>', '').replace('</b>', ''),
                    "category": item['category'].split('>')[-1] if item['category'] else "맛집",
                    "address": item['address'],
                    "link": item['link'] or f"https://search.naver.com/search.naver?query={item['title']}"
                })
            return jsonify({"items": results})
    except Exception as e:
        print(f"API Error: {e}")
        
    return jsonify({"error": "주변 맛집 정보를 가져오지 못했습니다."}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)