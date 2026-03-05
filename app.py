import os
import random
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Render 환경변수 설정 확인
CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

@app.route('/')
def index():
    # HTML에 Client ID를 넘겨주어야 지도를 로드할 수 있습니다.
    return render_template('index.html', client_id=CLIENT_ID)

@app.route('/recommend')
def recommend():
    query = request.args.get('query', '강남역 맛집')
    
    # 네이버 지역 검색 API (display: 5는 후보군 5개 가져오기)
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=5"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        if data.get('items'):
            # 5개 결과 중 하나를 무작위로 선택하여 재미 요소 부여
            place = random.choice(data['items'])
            
            # 카테고리 정리 (예: 음식점>한식 -> 한식)
            category = place['category'].split('>')[-1] if place['category'] else "맛집"
            
            return jsonify({
                "name": place['title'].replace('<b>', '').replace('</b>', ''),
                "category": category,
                "address": place['address'],
                "mapx": place['mapx'],
                "mapy": place['mapy'],
                "link": place['link']
            })
    except Exception as e:
        print(f"Error: {e}")
        
    return jsonify({"error": "주변 맛집을 찾지 못했습니다. 지역을 입력해 보세요!"}), 404

if __name__ == '__main__':
    # Render 배포를 위한 포트 설정
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)