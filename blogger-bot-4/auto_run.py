import time
import schedule
import keyword_research
import content_generator
import blogger_publisher

def job(theme):
    print(f"\n🚀 [예약 포스팅 시작] 테마: {theme} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        print(f"\n▶ STEP 1: 키워드 리서치 시작 (타겟 주제: {theme})")
        # 지정된 테마를 리서치 모듈로 전달합니다!
        keyword_research.main(theme)
        time.sleep(2)
        
        print("\n▶ STEP 2: AI 콘텐츠 생성 시작 (이미지 처리 포함)")
        content_generator.main()
        time.sleep(2)
        
        print("\n▶ STEP 3: 블로거 자동 발행 시작 (태그 적용)")
        blogger_publisher.main()
    except Exception as e:
        print(f"\n❌ 작업 중 에러 발생: {e}")
        
    print("\n🎉 [예약 포스팅 완료. 다음 시간을 대기합니다.]")

if __name__ == "__main__":
    print("🤖 블로그 봇이 24시간 상시 가동 모드로 전환되었습니다.")
    print("⏰ 세팅된 포스팅 시간: 매일 08:00(정부지원금), 13:00(생활팁), 19:00(건강)\n")
    
    # 🌟 여기서 던져주는 테마대로 뉴스를 수집하게 됩니다!
    schedule.every().day.at("08:00").do(job, theme="정부 지원금 및 주부 숨은 환급금 찾기")
    schedule.every().day.at("13:00").do(job, theme="주부 살림 노하우 및 살림 꿀팁")
    schedule.every().day.at("19:00").do(job, theme="중장년층 다이어트 및 질환 예방 건강 관리")

    # 봇을 끄지 않고 무한 대기시키는 로직
    while True:
        schedule.run_pending()
        time.sleep(1)