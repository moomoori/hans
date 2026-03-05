import feedparser
import json
import telebot # 설치 필요: pip install pyTelegramBotAPI
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# 설정
TOKEN = '8725258810:AAHuUDHdN-ER9WMrwuZdJ8TBZXbmAn5alx8'
CHAT_ID = '6095382920'
CONFIG_FILE = 'config.json'
bot = telebot.TeleBot(TOKEN)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if "apply_config" in call.data:
        # 버튼 데이터에서 설정값 파싱 (예: apply_config_0.05_30)
        _, _, risk, adx = call.data.split('_')
        new_config = {
            "RISK_RATIO": float(risk),
            "ADX_THRESHOLD": int(adx),
            "STOP_LOSS_PCT": 0.015,
            "COMMENT": f"뉴스 분석에 따른 원격 업데이트 ({datetime.now().strftime('%H:%M')})"
        }
        save_config(new_config)
        bot.answer_callback_query(call.id, "✅ 매매 봇 설정이 즉시 변경되었습니다!")
        bot.send_message(CHAT_ID, f"🚀 **[매매 봇 설정 동기화 완료]**\n- 리스크 비중: {risk}\n- ADX 필터: {adx}")

def send_strategy_report():
    # (뉴스 수집 로직 생략 - 이전과 동일)
    # ... 분석 결과에 따라 제안값 생성 ...
    suggested_risk = 0.05  # 예시: 변동성 클 때
    suggested_adx = 30
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ 위 설정으로 봇 업데이트 승인", 
               callback_query_data=f"apply_config_{suggested_risk}_{suggested_adx}"))
    
    report = "📊 **[2026 전략 제안]**\n변동성이 감지되었습니다. 리스크를 낮추고 필터를 강화할까요?"
    bot.send_message(CHAT_ID, report, reply_markup=markup, parse_mode="Markdown")

# 뉴스 봇 가동
bot.polling()
