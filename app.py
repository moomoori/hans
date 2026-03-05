import os
import random
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# 네이버 API 키 (Render 환경변수에서 가져옴)
CLIENT_ID = os.environ.get('NAVER_CLIENT_ID')
CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET')

@app.route('/')
def index():
    return render_template('index.html', client_id=CLIENT_ID)

@app.route('/recommend_v2')
def recommend_v2():
    # 클라이언트로부터 전달받은 주소와 음식 종류
    full_address = request.args.get('location', '서울 강남역')
    food = request.args.get('food', '맛집')
    
    # [핵심 수정] 검색 최적화 로직
    # "서울특별시 강남구 역삼동 825-13" -> "강남구 역삼동" 정도로 검색어 정제
    addr_parts = full_address.split()
    
    # 보통 주소의 2번째(구), 3번째(동) 단어가 검색에 가장 효율적입니다.
    if len(addr_parts) >= 3:
        optimized_addr = f"{addr_parts[1]} {addr_parts[2]}"
    elif len(addr_parts) == 2:
        optimized_addr = f"{addr_parts[0]} {addr_parts[1]}"
    else:
        optimized_addr = full_address

    query = f"{optimized_addr} {food}"
    
    # 서버 로그에서 어떤 검색어로 검색되는지 확인할 수 있습니다.
    print(f"--- Search Debug ---")
    print(f"Original: {full_address}")
    print(f"Optimized Query: {query}")
    
    # 네이버 지역 검색 API 호출 (리뷰 순 정렬 가중치)
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=10&sort=comment"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        
        if data.get('items'):
            # 상위 5개 결과 추출 및 데이터 가공
            items = data['items'][:5]
            results = []
            for item in items:
                # <b> 태그 제거 등 텍스트 정리
                clean_name = item['title'].replace('<b>', '').replace('</b>', '')
                category = item['category'].split('>')[-1] if item['category'] else "맛집"
                
                results.append({
                    "name": clean_name,
                    "category": category,
                    "address": item['address'],
                    "link": item['link'] if item['link'] else f"https://search.naver.com/search.naver?query={clean_name}"
                })
            return jsonify({"items": results})
        else:
            # 검색 결과가 아예 없을 경우 빈 리스트 반환
            return jsonify({"items": []})
            
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({"error": "API 호출 중 오류가 발생했습니다."}), 500

if __name__ == '__main__':
    # Render 환경의 포트 설정 대응
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)