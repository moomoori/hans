import pyupbit
import pandas as pd
import time
import logging
import requests
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# --- 설정값 (본인 정보 입력) ---
ACCESS_KEY = "k1WIYvWe1RoJ0o1hUcV0abfe8YlJ0WyxXupsbAiZ"
SECRET_KEY = "wTmx5nHHULCxNuoBsnJyOnZ1w54F8cf0Si5xUNA6"
TELEGRAM_TOKEN = "8701314668:AAHdmgqsmucn0q96dau_DJt8ReLW9qjLlYQ"
CHAT_ID = "6095382920"

# 매매 전략 파라미터
MAX_LOSS_PERCENT = 1.5      # 손절 -1.5%
SAFE_PROFIT_TRIGGER = 3.0   # 1.2% 찍으면 본전방어 가동
SCAN_INTERVAL = 3600
JOURNAL_FILE = "trading_journal.csv"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
upbit = pyupbit.Upbit(ACCESS_KEY, SECRET_KEY)

# ==========================================
# 2. 유틸리티 함수
# ==========================================

def send_tg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.get(url, params=params, timeout=5)
    except Exception as e:
        logging.error(f"텔레그램 전송 실패: {e}")

def get_total_asset():
    """에러가 발생한 종목은 건너뛰고 나머지 자산만 합산하는 안전 버전"""
    try:
        balances = upbit.get_balances()
        if not isinstance(balances, list):
            return 0
            
        total = 0
        for b in balances:
            try:
                if b['currency'] == "KRW":
                    total += float(b['balance']) + float(b['locked'])
                else:
                    ticker = f"KRW-{b['currency']}"
                    # 개별 종목 조회 시 에러가 나면 해당 종목만 패스함
                    price = pyupbit.get_current_price(ticker)
                    if price is not None:
                        total += (float(b['balance']) + float(b['locked'])) * price
                    else:
                        logging.warning(f"⚠️ {ticker} 가격 조회 실패 (상장폐지 혹은 코드 미지원)")
            except Exception as inner_e:
                # 특정 코인 하나 때문에 전체 합산이 멈추지 않도록 예외 처리
                logging.error(f"❌ {b['currency']} 계산 중 제외됨: {inner_e}")
                continue
                
        return total
    except Exception as e:
        logging.error(f"❌ 총 자산 시스템 치명적 에러: {e}")
        return 0

def write_journal(ticker, side, price, amount, profit_pct=0, profit_cash=0):
    """매매 내역을 엑셀(CSV) 파일에 기록"""
    df_new = pd.DataFrame([{
        '시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '종목': ticker,
        '구분': side,
        '가격': price,
        '수량': amount,
        '수익률(%)': profit_pct,
        '수익금(원)': profit_cash
    }])
    if not os.path.exists(JOURNAL_FILE):
        df_new.to_csv(JOURNAL_FILE, index=False, encoding='utf-8-sig')
    else:
        df_new.to_csv(JOURNAL_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

def weekly_report():
    """매주 일요일 밤 12시 주간 결산 보고"""
    try:
        if not os.path.exists(JOURNAL_FILE):
            send_tg("📊 이번 주 매매 기록이 없습니다.")
            return

        df = pd.read_csv(JOURNAL_FILE)
        df['시간'] = pd.to_datetime(df['시간'])
        
        # 최근 7일 데이터 필터링
        one_week_ago = datetime.now() - pd.Timedelta(days=7)
        weekly_df = df[df['시간'] >= one_week_ago]
        
        sell_df = weekly_df[weekly_df['구분'].isin(['익절', '손절', '본전방어'])]
        
        total_profit = sell_df['수익금(원)'].sum()
        avg_pct = sell_df['수익률(%)'].mean()
        win_rate = (len(sell_df[sell_df['수익금(원)'] > 0]) / len(sell_df) * 100) if len(sell_df) > 0 else 0
        
        report = (f"📅 [주간 결산 보고]\n\n"
                  f"💰 총 수익: {total_profit:,.0f}원\n"
                  f"📈 평균 수익률: {avg_pct:.2f}%\n"
                  f"🏆 승률: {win_rate:.1f}%\n"
                  f"🔄 매매 횟수: {len(sell_df)}회")
        
        send_tg(report)
    except Exception as e:
        logging.error(f"주간 보고 생성 에러: {e}")

# 주간 스케줄러 설정 (일요일 24시 = 월요일 00시)
scheduler = BackgroundScheduler()
scheduler.add_job(weekly_report, 'cron', day_of_week='mon', hour=0, minute=0)
scheduler.start()

# ... (get_top_tickers, get_btc_status, get_signals 함수는 기존과 동일) ...
def get_top_tickers():
    """어떤 응답 형식(List/Dict)에서도 거래대금 상위 5개를 완벽하게 추출합니다."""
    try:
        # 1. KRW 종목 리스트 가져오기
        tickers = pyupbit.get_tickers(fiat="KRW")
        
        # 2. 모든 종목의 상세 정보 가져오기 (거래대금 포함)
        snapshot = pyupbit.get_current_price(tickers, verbose=True)
        
        if not snapshot:
            return ["KRW-BTC", "KRW-XRP", "KRW-SOL", "KRW-ETH", "KRW-DOGE"]

        # 3. 데이터 형식 판별 및 리스트화
        # 딕셔너리로 왔을 경우 리스트로 변환, 이미 리스트라면 그대로 사용
        if isinstance(snapshot, dict):
            combined_data = []
            for ticker, info in snapshot.items():
                info['ticker'] = ticker # 종목명을 데이터 안에 삽입
                combined_data.append(info)
        else:
            combined_data = snapshot

        # 4. 거래대금(acc_trade_price_24h) 기준 내림차순 정렬
        # 데이터가 불완전할 경우를 대비해 get()으로 안전하게 가져옴
        sorted_data = sorted(
            combined_data, 
            key=lambda x: x.get('acc_trade_price_24h', 0) if isinstance(x, dict) else 0, 
            reverse=True
        )

        # 5. 상위 5개 종목 코드만 추출
        top_5 = []
        for item in sorted_data[:5]:
            if 'market' in item: # 리스트 형태 응답일 때
                top_5.append(item['market'])
            elif 'ticker' in item: # 딕셔너리 변환 형태일 때
                top_5.append(item['ticker'])

        logging.info(f"✅ 종목 스캔 성공: {', '.join(top_5)}")
        return top_5

    except Exception as e:
        logging.error(f"⚠️ 종목 스캔 중 에러 발생: {e}")
        # 어떤 상황에서도 봇이 멈추지 않게 기본값 반환
        return ["KRW-BTC", "KRW-XRP", "KRW-SOL", "KRW-ETH", "KRW-DOGE"]

def get_btc_status():
    try:
        df = pyupbit.get_ohlcv("KRW-BTC", interval="minute5", count=3)
        return df['close'].iloc[-1] >= df['close'].iloc[-2]
    except: return False

def get_signals(ticker):
    try:
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=100)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df['bull_ob'] = (df['close'].shift(1) < df['open'].shift(1)) & (df['close'] > df['open'].shift(1))
        df['channel_low'] = df['low'].rolling(20).min()
        df['channel_high'] = df['high'].rolling(20).max()
        return df.iloc[-1]
    except: return None

# ==========================================
# 3. 메인 트레이딩 루프
# ==========================================

def run_trading_bot():
    last_scan_time = 0
    current_tickers = []
    
    send_tg("🤖 [데이터 기록형] 봇 가동\n잔액 추적 및 주간 보고 시스템 활성화")

    while True:
        if time.time() - last_scan_time > SCAN_INTERVAL:
            current_tickers = get_top_tickers()
            last_scan_time = time.time()
            send_tg(f"🔍 종목 갱신: {', '.join(current_tickers)}")

        is_btc_safe = get_btc_status()

        for ticker in current_tickers:
            try:
                data = get_signals(ticker)
                if data is None: continue

                curr_price = data['close']
                rsi = data['rsi']
                balances = upbit.get_balances()
                coin_symbol = ticker.split('-')[1]
                coin_info = next((b for b in balances if b['currency'] == coin_symbol), None)

                # 매수 로직
                if coin_info is None or float(coin_info['balance']) * curr_price < 5000:
                    if not is_btc_safe: continue
                    
                    buy_score = 0
                    if rsi < 38: buy_score += 1
                    if data['bull_ob']: buy_score += 1
                    if curr_price <= data['channel_low'] * 1.01: buy_score += 1

                    if buy_score >= 2:
                        krw_bal = next((float(b['balance']) for b in balances if b['currency'] == "KRW"), 0)
                        if krw_bal > 5000:
                            buy_amount = krw_bal * 0.2
                            res = upbit.buy_market_order(ticker, buy_amount)
                            if res:
                                write_journal(ticker, "매수", curr_price, buy_amount)
                                total_asset = get_total_asset()
                                send_tg(f"🚀 [{ticker}] 매수\n단가: {curr_price:,.0f}원\n💰 총자산: {total_asset:,.0f}원")

                # 매도 로직 (손절/익절 강화 버전)
                else:
                    coin_bal = float(coin_info['balance'])
                    avg_buy_price = float(coin_info['avg_buy_price'])
                    profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                    profit_cash = (curr_price - avg_buy_price) * coin_bal

                    sell_type = None
                    
                    # 1. 손절 조건 (무조건 -1.5% 도달 시)
                    if profit_rate <= -MAX_LOSS_PERCENT: 
                        sell_type = "손절"
                    
                    # 2. 익절 조건 (최소 3% 이상 수익권일 때만 발동)
                    elif profit_rate >= SAFE_PROFIT_TRIGGER:
                        # 수익권이면서 + (RSI가 70 이상 과매수거나 OR 채널 상단에 거의 닿았을 때)
                        if rsi >= 70 or curr_price >= data['channel_high'] * 0.99:
                            sell_type = "익절"
                        
                        # (선택사항) 만약 수익이 7% 등 너무 높으면 기술적 지표 상관없이 분할 익절하고 싶다면 추가 가능
                        # elif profit_rate >= 7.0:
                        #     sell_type = "강제익절"

                    if sell_type:
                        res = upbit.sell_market_order(ticker, coin_bal)
                        if res:
                            write_journal(ticker, sell_type, curr_price, coin_bal, profit_rate, profit_cash)
                            total_asset = get_total_asset()
                            icon = "🚨" if sell_type == "손절" else "💰"
                            send_tg(f"{icon} [{ticker}] {sell_type}\n수익률: {profit_rate:.2f}%\n수익금: {profit_cash:,.0f}원\n💰 총자산: {total_asset:,.0f}원")
                            
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"{ticker} 에러: {e}")
        time.sleep(10)

if __name__ == "__main__":
    run_trading_bot()
