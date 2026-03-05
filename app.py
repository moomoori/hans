import os
from flask import Flask, render_template, jsonify
import requests
import random

app = Flask(__name__)

# 네이버 API 설정 (Render의 Environment 탭에 등록하세요)
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

def get_random_restaurant(location="강남역", keyword="맛집"):
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": f"{location} {keyword}",
        "display": 5  # 5개 검색 결과 중 랜덤 선택
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get('items', [])
        if results:
            return random.choice(results)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recommend')
def recommend():
    restaurant = get_random_restaurant()
    if restaurant:
        # 네이버는 제목에 <b> 태그가 포함되므로 제거
        clean_name = restaurant['title'].replace('<b>', '').replace('</b>', '')
        return jsonify({
            "name": clean_name,
            "category": restaurant['category'],
            "address": restaurant['address'],
            "link": restaurant['link']
        })
    return jsonify({"error": "맛집을 찾을 수 없습니다."}), 404
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
