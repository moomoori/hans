import os
import requests
from flask import Flask, render_template, jsonify, request
from urllib.parse import quote

app = Flask(__name__)

# 네이버 개발자 센터에서 발급받은 ID와 Secret (Render 환경변수에 설정하세요)
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recommend_v2')
def recommend_v2():
    location = request.args.get('location', '')
    food = request.args.get('food', '맛집')
    start = request.args.get('start', 1, type=int)
    
    # 검색 쿼리: "역삼동 한식"
    query = f"{location} {food}"

    # 네이버 지역 검색 API (sort=comment: 리뷰/인기순)
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=10&start={start}&sort=comment"
    
    headers = {
        "X-Naver-Client-Id": SEARCH_ID,
        "X-Naver-Client-Secret": SEARCH_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return jsonify({"items": []})
            
        data = res.json()
        items = data.get('items', [])
        
        results = []
        for item in items:
            clean_name = item['title'].replace('<b>', '').replace('</b>', '')
            address = item['address']
            
            # [핵심] 네이버 지도 검색 URL 생성: 가게명 + 주소를 합쳐서 정확도 극대화
            search_combined = f"{clean_name} {address}"
            map_url = f"https://map.naver.com/v5/search/{quote(search_combined)}"
            
            results.append({
                "name": clean_name,
                "category": item['category'].split('>')[-1],
                "address": address,
                "map_url": map_url
            })
        return jsonify({"items": results})
            
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"items": []})

if __name__ == '__main__':
    # Render는 기본적으로 10000 포트를 사용합니다
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)