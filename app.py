from flask import Flask, render_template, jsonify
import requests
import random

app = Flask(__name__)

# 카카오 API 설정 (본인의 REST API 키를 입력하세요)
KAKAO_API_KEY = os.environ.get("KAKAO_API_KEY")

def get_random_restaurant(location="강남역", keyword="맛집"):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": f"{location} {keyword}", "category_group_code": "FD6"}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get('documents', [])
        if results:
            return random.choice(results) # 검색 결과 중 랜덤 하나 추출
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/recommend')
def recommend():
    # 실제로는 위치 정보를 브라우저에서 받아올 수 있지만, 우선 강남역 기준으로 테스트
    restaurant = get_random_restaurant()
    if restaurant:
        return jsonify({
            "name": restaurant['place_name'],
            "category": restaurant['category_name'].split(' > ')[-1],
            "address": restaurant['address_name'],
            "url": restaurant['place_url']
        })
    return jsonify({"error": "맛집을 찾을 수 없습니다."}), 404

if __name__ == '__main__':
    # 서버에서 지정한 포트(PORT)를 사용하고, 없으면 5000번 사용
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)