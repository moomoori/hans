import os
import random
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

@app.route('/')
def index():
    return render_template('index.html', client_id=CLIENT_ID)

@app.route('/recommend_v2')
def recommend_v2():
    # 주소(위치)와 음식 종류를 합쳐서 검색
    location = request.args.get('location', '내 주변')
    food = request.args.get('food', '맛집')
    query = f"{location} {food}"
    
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=10&sort=comment"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        if data.get('items'):
            # 리뷰가 많은 순으로 가져온 뒤 5개 추출
            items = data['items'][:5]
            results = []
            for item in items:
                results.append({
                    "name": item['title'].replace('<b>', '').replace('</b>', ''),
                    "category": item['category'].split('>')[-1],
                    "address": item['address'],
                    "link": item['link']
                })
            return jsonify({"items": results})
    except Exception as e:
        print(e)
        
    return jsonify({"error": "주변 맛집을 찾지 못했습니다."}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)