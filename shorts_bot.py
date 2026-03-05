import os
import time
import datetime
import pickle
import requests
from bs4 import BeautifulSoup
from gtts import gTTS

# 최신 라이브러리 임포트 규격
from moviepy import TextClip, AudioFileClip, ImageClip, CompositeAudioClip, CompositeVideoClip, ColorClip
from google import genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ==========================================
# 1. 환경 설정 (본인 정보 입력)
# ==========================================
GEMINI_API_KEY = "AIzaSyAcD7g1MO4hoo2J2QZrrRk8ZIWAig2_Zt0"
PEXELS_API_KEY = "Vq26joQjrbatRuYf2jtRlf1aFldqxXZEIDZWL9zGDNx2arpnhjR0tQxH"
CLIENT_SECRET_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Gemini 클라이언트 (최신 v2.0-flash 모델 사용)
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. 유튜브 인증 함수 (리눅스 서버 최적화)
# ==========================================
def get_youtube_service():
    creds = None
    # 이전에 저장된 인증 토큰이 있는지 확인
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 인증 정보가 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            # 리눅스 서버용: 브라우저를 띄우지 않고 터미널에 URL만 출력
            print("\n" + "="*50)
            print(" 아래 URL을 복사하여 PC 브라우저에서 접속 후 인증하세요:")
            creds = flow.run_local_server(port=8080, open_browser=False)
            print("="*50 + "\n")
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('youtube', 'v3', credentials=creds)

# ==========================================
# 3. 제작 및 수집 함수
# ==========================================
def get_hot_news():
    url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, 'xml')
    item = soup.find_all('item')[0]
    return item.title.text

def get_free_image(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1&orientation=portrait"
    try:
        res = requests.get(url, headers=headers).json()
        img_url = res['photos'][0]['src']['large2x']
        with open("temp_bg.jpg", 'wb') as f:
            f.write(requests.get(img_url).content)
        return "temp_bg.jpg"
    except:
        return None

def create_video(title, script):
    # 음성 생성
    tts = gTTS(text=script, lang='ko')
    tts.save("temp_voice.mp3")
    audio = AudioFileClip("temp_voice.mp3")

    # 이미지 검색어 추출 (Gemini)
    response = client_gemini.models.generate_content(
        model="gemini-2.0-flash", 
        contents=f"'{title}' 뉴스와 어울리는 이미지 검색용 영어 단어 1개만 말해줘."
    )
    search_q = response.text.strip()
    img_path = get_free_image(search_q)

    # 배경 영상 조립
    if img_path:
        bg = ImageClip(img_path).with_duration(audio.duration).resized(height=1920)
    else:
        bg = ColorClip(size=(1080, 1920), color=(0,0,0)).with_duration(audio.duration)

    # 자막 (메인 뉴스 제목)
    txt = TextClip(text=title, font_size=60, color='yellow', bg_color='black', 
                   method='caption', size=(900, None)).with_duration(audio.duration).with_position(('center', 1400))

    # 오디오 합성
    final_audio = audio
    if os.path.exists("bgm.mp3"):
        bgm = AudioFileClip("bgm.mp3").multiply_volume(0.1).with_duration(audio.duration)
        final_audio = CompositeAudioClip([audio, bgm])

    # 최종 출력
    final_video = CompositeVideoClip([bg, txt]).with_audio(final_audio)
    final_video.write_videofile("shorts_final.mp4", fps=24, codec="libx264")
    return "shorts_final.mp4"

def upload_video(youtube, file_path, title):
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"[실시간 뉴스] {title}"[:70],
                "description": "AI가 매시간 가장 핫한 뉴스를 전해드립니다. #shorts #news",
                "categoryId": "22"
            },
            "status": {"privacyStatus": "public"}
        },
        media_body=MediaFileUpload(file_path)
    )
    response = request.execute()
    print(f"✅ 업로드 완료! 영상 ID: {response.get('id')}")

# ==========================================
# 4. 실행 루프
# ==========================================
if __name__ == "__main__":
    print("🚀 뉴스 숏츠 자동 업로드 봇 작동 중...")
    youtube_service = get_youtube_service() # 최초 1회 인증 실행
    
    while True:
        now = datetime.datetime.now()
        if now.hour in [8, 12, 18] and now.minute == 0:
            try:
                title = get_hot_news()
                print(f"🎬 {now.hour}시 작업 시작: {title}")
                
                # 대본 생성
                prompt = f"'{title}' 뉴스로 40초 분량의 긴박한 유튜브 숏츠 대본만 써줘. 군더더기 없이 대사만 출력해."
                script_res = client_gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                script = script_res.text
                
                # 제작 및 업로드
                video_file = create_video(title, script)
                upload_video(youtube_service, video_file, title)
                
                print("💤 완료! 다음 스케줄까지 대기합니다.")
                time.sleep(3600)
            except Exception as e:
                print(f"❌ 에러 발생: {e}")
                time.sleep(60)
        
        time.sleep(30)