import os
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# 지도용 ID (화면에 전달)
NCP_ID = os.environ.get('NCP_CLIENT_ID')
# 검색용 키 (개발자 센터용)
SEARCH_ID = os.environ.get('NAVER_SEARCH_ID')
SEARCH_SECRET = os.environ.get('NAVER_SEARCH_SECRET')

@app.route('/')
def index():
    # 지도는 NCP 키를 사용해야 하므로 NCP_ID를 넘겨줌
    return render_template('index.html', client_id=NCP_ID)

@app.route('/recommend_v2')
def recommend_v2():
    full_address = request.args.get('location', '')
    food = request.args.get('food', '맛집')
    
    # 주소 정제 (구 동 단위)
    addr_parts = full_address.split()
    query_addr = " ".join(addr_parts[1:3]) if len(addr_parts) >= 3 else full_address
    query = f"{query_addr} {food}"

    # 개발자 센터 검색 API 주소
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display=5&sort=comment"
    headers = {
        "X-Naver-Client-Id": SEARCH_ID,
        "X-Naver-Client-Secret": SEARCH_SECRET
    }
    
    try:
        res = requests.get(url, headers=headers)
        # 개발자 센터 API는 결과가 없거나 키가 틀리면 에러 코드를 보냅니다.
        if res.status_code != 200:
            print(f"Search API Error: {res.status_code}, {res.text}")
            return jsonify({"items": []})
            
        data = res.json()
        items = data.get('items', [])
        
        results = []
        for item in items:
            results.append({
                "name": item['title'].replace('<b>', '').replace('</b>', ''),
                "category": item['category'].split('>')[-1],
                "address": item['address'],
                "link": item['link'] if item['link'] else f"https://search.naver.com/search.naver?query={item['title']}"
            })
        return jsonify({"items": results})
            
    except Exception as e:
        print(f"Python Error: {e}")
        return jsonify({"items": []})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)