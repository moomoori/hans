# keyword_research.py ― AI 브레인스토밍 타겟 키워드 기획기

import time
import requests
import json
import re
import pandas as pd

# ════════════════ 설정 ════════════════
GEMINI_API_KEY = "AIzaSyBnI_LNy5658c9NlsvymFgrdGUIy-UFhbE" 
MODEL_NAME = "gemini-3.1-flash-lite-preview"
TOP_N = 3 # 뽑아낼 세부 키워드 개수
# ══════════════════════════════════════

def generate_keywords_with_ai(theme):
    print(f"  🤖 제미나이에게 '{theme}' 관련 어그로 키워드 기획 요청 중...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}

    prompt = f"""
    당신은 월 방문자 100만 명을 기록하는 파워블로거이자 트렌드 기획자입니다.
    오늘의 메인 테마는 '{theme}'입니다.
    이 테마에 맞춰, 사람들이 당장 검색해서 들어올 만한 아주 구체적이고 호기심을 자극하는 세부 키워드(글감) {TOP_N}개를 뽑아주세요.
    (예: 다이소 품절대란 청소템 3가지, 2026년 숨은 정부지원금 찾기 등)

    반드시 아래 JSON 배열 형식으로만 대답해주세요. 다른 말은 절대 하지 마세요.
    ["키워드1", "키워드2", "키워드3"]
    """

    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    # 🌟 503 에러 방어: 최대 3번까지 끈질기게 재시도합니다!
    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json=data)
            if res.status_code == 200:
                result = res.json()
                text = result['candidates'][0]['content']['parts'][0]['text']
                text = re.sub(r"^```json\s*|^```\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
                # strict=False를 넣어 특수문자 에러까지 완벽 방어!
                return json.loads(text, strict=False)
            elif res.status_code == 503:
                print(f"  서버 혼잡(503)... {attempt+1}번째 재시도 중")
                time.sleep(5)
            else:
                print(f"  ❌ API 에러: {res.text}")
                return []
        except Exception as e:
            print(f"  ❌ 에러 발생: {e}")
            return []
            
    print("  ❌ 3번 재시도했지만 서버가 너무 바쁩니다.")
    return []

# 👇 여기가 핵심입니다! topic을 받을 수 있게 문을 열어두었습니다.
def main(topic="IT"):
    print(f"=== AI 기반 타겟 키워드 리서치 시작 (주제: {topic}) ===\n")
    
    ai_keywords = generate_keywords_with_ai(topic)
    
    if not ai_keywords:
        print("키워드 수집에 실패했습니다. 기본 키워드로 대체합니다.")
        ai_keywords = [f"{topic} 핵심 꿀팁", f"{topic} 최신 트렌드", f"알아두면 돈이 되는 {topic}"]

    all_data = [{"keyword": kw, "score": 100, "source": "Gemini_AI"} for kw in ai_keywords]

    df = pd.DataFrame(all_data)
    df.index += 1
    
    df.to_csv("keywords.csv", encoding="utf-8-sig")
    print(f"\n=== 완료! 상위 {len(df)}개 기획 키워드를 keywords.csv에 저장 ===\n")
    print(df[["keyword", "source"]].to_string())

if __name__ == "__main__":
    main("주부 살림 노하우 및 다이소 가성비 꿀팁")