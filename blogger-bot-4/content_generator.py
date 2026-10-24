import os, re, json, time, requests, pandas as pd
from datetime import datetime
from pathlib import Path

# ════════════════ 설정 ════════════════
GEMINI_API_KEY = "AIzaSyBnI_LNy5658c9NlsvymFgrdGUIy-UFhbE" 
MODEL_NAME = "gemini-3.1-flash-lite-preview"
POSTS_PER_RUN = 3
UNSPLASH_ACCESS_KEY = "2AAiP6J-WwRdtmlStDJOpGNzl9silt5punT_eCkMQNY"

OUTPUT_DIR = Path("posts")
OUTPUT_DIR.mkdir(exist_ok=True)
# ══════════════════════════════════════

def get_image_html(eng_keyword):
    print(f"  📸 '{eng_keyword}' 이미지 찰칵!")
    url = f"https://api.unsplash.com/search/photos?page=1&query={eng_keyword}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if data['results']:
                img_url = data['results'][0]['urls']['regular']
                return f'<p><img src="{img_url}" alt="{eng_keyword}" style="max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 20px;"></p>\n\n'
    except Exception as e:
        print(f"  이미지 가져오기 실패: {e}")
    return "" 

def generate_post_direct(keyword):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # 🌟 프롬프트 수정: 추상적 단어(감정) 절대 금지, 구체적인 사물 명사만 사용하도록 강력 통제!
    prompt = f"""
    당신은 월 방문자 100만 명을 보유한 엄청난 텐션의 파워블로거이자 트렌드 1타 강사입니다. 
    오늘 다룰 핵심 키워드는 '{keyword}'입니다. 
    이 키워드를 가지고 당장 유튜브 영상 스크립트로 써도 될 만큼, 독자의 시선을 확 끄는(어그로성 있는) 1500자 이상의 블로그 글을 JSON 형식으로 작성해 주세요.

    [작성 가이드라인 - 무조건 지킬 것]
    1. 말투: "~습니다", "~합니다" 같은 딱딱한 문어체 금지! "~요", "~죠", "대박이지 않나요?" 등 카메라 앞에서 수다 떨듯 친근한 말투 사용.
    2. 본문 구성: <h2>, <h3> 태그를 적극 활용하여 문단을 나누세요.
    3. 🌟 이미지 삽입 규칙 (가장 중요!): 
       각 <h2> 또는 <h3> 소제목 아래에 해당 문단에서 소개하는 '실제 아이템'과 매칭되는 Unsplash 검색용 태그를 넣으세요.
       - 🚫 절대 금지: shock, surprise, money, cheap, idea, secret 같은 추상적인 단어나 감정 표현은 절대 쓰지 마세요.
       - ✅ 필수 사용: 소개하는 아이템의 형태를 보여주는 직관적이고 구체적인 영문 사물 명사만 사용하세요. (예: sponge, storage box, cleaning brush, kitchen towel, soap)
       - 형식: [IMAGE: 구체적인 영문 사물 명사 1~2단어] 
       주의: 반드시 본문 전체에 걸쳐 최소 3~4개의 서로 다른 아이템 [IMAGE: 영문단어] 태그가 골고루 들어가야 합니다.
    4. 강조 표현: 중요한 내용은 <strong> 태그로 굵게 처리하세요.
    
    [출력 JSON 형식]
    {{
        "title": "[유튜브 썸네일 스타일의 자극적이고 클릭하고 싶은 제목]",
        "content_html": "<h2>1. 찌든 때 녹이는 마법의 가루</h2>\n[IMAGE: baking soda]\n<p>내용...</p>\n<h2>2. 싱크대 물때 청소템</h2>\n[IMAGE: cleaning sponge]\n<p>내용...</p>",
        "meta_description": "검색 결과에 노출될 150자 이내의 흥미진진한 요약본"
    }}
    """
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    for attempt in range(5): 
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            break
        elif res.status_code == 503:
            wait_time = 10 + (attempt * 5) # 10초, 15초, 20초... 점점 길게 쉼
            print(f"  서버 혼잡(503)... {wait_time}초 대기 후 {attempt+1}번째 재시도 중")
            time.sleep(wait_time) 
        else:
            raise Exception(f"API 호출 실패: {res.text}")
            
    if res.status_code != 200:
        raise Exception(f"API 호출 실패: {res.text}")
        
    result = res.json()
    text = result['candidates'][0]['content']['parts'][0]['text']
    text = re.sub(r"^```json\s*|^```\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text, strict=False)

def main():
    print("=== 블로그 콘텐츠 생성 시작 (이미지 싱크로율 강화 버전) ===\n")
    df = pd.read_csv("keywords.csv", encoding="utf-8-sig")
    keywords = df['keyword'].tolist()[:POSTS_PER_RUN]

    for i, keyword in enumerate(keywords, 1):
        print(f"[{i}/{len(keywords)}] '{keyword[:15]}' 작업 중...")
        try:
            post = generate_post_direct(keyword)
            
            def replacer(match):
                eng_keyword = match.group(1)
                return get_image_html(eng_keyword)
            
            # [IMAGE: storage box] 같이 띄어쓰기가 포함된 사물 명사도 잡을 수 있도록 정규식 수정
            content_with_images = re.sub(r"\[IMAGE:\s*([a-zA-Z0-9_ -]+)\]", replacer, post['content_html'])
            
            final_html = f"<h1>{post['title']}</h1>\n{content_with_images}"
            
            safe_name = re.sub(r"[^\w가-힣]", "_", keyword)[:30]
            with open(OUTPUT_DIR / f"{safe_name}.html", "w", encoding="utf-8") as f:
                f.write(final_html)
                
            print(f"  ✅ 성공: {post['title']}")
            
            if i < len(keywords): time.sleep(30)
            
        except Exception as e:
            print(f"  ❌ 오류: {e}")

if __name__ == "__main__":
    main()