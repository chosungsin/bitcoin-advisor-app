import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime
import pyupbit

st.set_page_config(page_title="비트코인 매수/매도 타이밍 AI 분석기", layout="wide")

@st.cache_data(ttl=3600)
def get_fear_and_greed():
    """Alternative.me에서 공포/탐욕 지수를 가져옵니다."""
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1")
        data = response.json()
        return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except:
        return 50, "Unknown"

def calculate_indicators(df):
    """선택된 데이터프레임에 보조지표(RSI, MACD, 볼린저밴드)를 계산합니다."""
    # RSI (14)
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=True, min_periods=14).mean()
    ma_down = down.ewm(com=13, adjust=True, min_periods=14).mean()
    rsi = ma_up / ma_down
    df['RSI'] = 100 - (100 / (1 + rsi))
    
    # EMA 20, 50
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # 볼린저 밴드 (20, 2)
    df['BB_MA20'] = df['close'].rolling(window=20).mean()
    df['BB_STD'] = df['close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_MA20'] + (df['BB_STD'] * 2)
    df['BB_Lower'] = df['BB_MA20'] - (df['BB_STD'] * 2)
    
    return df

@st.fragment(run_every="1s")
def render_realtime_orderbook():
    """1초마다 실행되어 호가창과 현재가를 실시간 업데이트하는 조각"""
    try:
        krw_price = pyupbit.get_current_price("KRW-BTC")
        orderbooks = pyupbit.get_orderbook("KRW-BTC")
    except:
        krw_price = 0
        orderbooks = None
        
    st.markdown(f"### ⚡ 업비트 현재가: <span style='color:#00cc96;'>₩{krw_price:,.0f}</span>", unsafe_allow_html=True)
    
    if orderbooks and 'orderbook_units' in orderbooks:
        units = orderbooks['orderbook_units']
        st.markdown("**(단위: KRW / BTC)**")
        
        for unit in reversed(units[:10]):
            ask_price = unit['ask_price']
            ask_size = unit['ask_size']
            st.markdown(f"<div style='background-color:rgba(255, 75, 75, 0.2); padding:5px; border-radius:5px; margin-bottom:2px; display:flex; justify-content:space-between;'>"
                        f"<span style='color:#ff4b4b; font-weight:bold;'>{ask_price:,.0f}</span>"
                        f"<span>{ask_size:.4f}</span>"
                        f"</div>", unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 10px 0; border-color: gray;'>", unsafe_allow_html=True)
        
        for unit in units[:10]:
            bid_price = unit['bid_price']
            bid_size = unit['bid_size']
            st.markdown(f"<div style='background-color:rgba(0, 204, 150, 0.2); padding:5px; border-radius:5px; margin-bottom:2px; display:flex; justify-content:space-between;'>"
                        f"<span style='color:#00cc96; font-weight:bold;'>{bid_price:,.0f}</span>"
                        f"<span>{bid_size:.4f}</span>"
                        f"</div>", unsafe_allow_html=True)
    else:
        st.warning("호가창 데이터를 불러올 수 없습니다.")
        
    st.caption(f"호가창 업데이트: {datetime.now().strftime('%H:%M:%S')}")

@st.fragment(run_every="5s")
def render_realtime_chart(interval_val, interval_name):
    """5초마다 실행되어 선택한 타임프레임의 차트와 시그널을 업데이트하는 조각"""
    df_chart = pyupbit.get_ohlcv("KRW-BTC", interval=interval_val, count=100)
    
    if df_chart is not None and not df_chart.empty:
        df_chart = calculate_indicators(df_chart)
        
        current_price = df_chart['close'].iloc[-1]
        current_rsi = df_chart['RSI'].iloc[-1]
        current_ema20 = df_chart['EMA20'].iloc[-1]
        bb_upper = df_chart['BB_Upper'].iloc[-1]
        bb_lower = df_chart['BB_Lower'].iloc[-1]
        
        # --- AI 투자 시그널 분석 ---
        st.header(f"🤖 AI 투자 시그널 ({interval_name} 기준)")
        
        signal = "관망 (Hold)"
        color = "gray"
        reason = []
        
        if current_rsi > 70 or current_price >= bb_upper:
            signal = "🚨 강력 매도 / 차익 실현 (Sell)"
            color = "#ff4b4b" 
            if current_rsi > 70:
                reason.append(f"RSI가 {current_rsi:.1f}로 '과매수' 구간에 진입했습니다.")
            if current_price >= bb_upper:
                reason.append("가격이 볼린저 밴드 상단을 돌파하여 단기 조정 확률이 매우 높습니다.")
            reason.append("추격 매수를 삼가고 보유 물량의 분할 매도를 권장합니다.")
        elif current_rsi < 30 or current_price <= bb_lower:
            signal = "💰 강력 매수 기회 (Buy)"
            color = "#00cc96" 
            if current_rsi < 30:
                reason.append(f"RSI가 {current_rsi:.1f}로 '과매도' 구간에 진입했습니다.")
            if current_price <= bb_lower:
                reason.append("가격이 볼린저 밴드 하단을 이탈하여 기술적 반등이 예상됩니다.")
            reason.append("저점 분할 매수를 적극 고려해볼 수 있는 타점입니다.")
        elif current_price > current_ema20:
            signal = "📈 상승 추세 유지 - 분할 매수 / 홀딩"
            color = "#ffa15a" 
            reason.append("가격이 20일선(EMA) 위에서 안정적으로 지지받으며 상승 채널을 유지 중입니다.")
            reason.append(f"현재 RSI는 {current_rsi:.1f}로 과열되지 않은 상태입니다.")
        else:
            signal = "📉 하락/횡보 추세 - 관망"
            color = "#636efa" 
            reason.append("가격이 20일선(EMA) 아래에 머물러 있어 매도 압력이 더 강합니다.")
            reason.append("확실한 추세 전환(20일선 돌파)이 나올 때까지 현금을 관망하는 것이 좋습니다.")
            
        st.markdown(f"<h2 style='color: {color};'>{signal}</h2>", unsafe_allow_html=True)
        
        st.subheader("💡 판단 근거 상세")
        for r in reason:
            st.write(f"- {r}")

        # --- 차트 그리기 ---
        st.subheader(f"📊 비트코인 차트")
        fig = go.Figure()
        
        # 캔들스틱
        fig.add_trace(go.Candlestick(x=df_chart.index,
                    open=df_chart['open'], high=df_chart['high'],
                    low=df_chart['low'], close=df_chart['close'], 
                    increasing_line_color='#ff4b4b', decreasing_line_color='#636efa',
                    name='KRW-BTC'))
                    
        # 이동평균선 및 볼린저 밴드
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA20'], line=dict(color='orange', width=1.5), name='EMA 20'))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_Upper'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), name='BB 상단'))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_Lower'], line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dot'), name='BB 하단', fill='tonexty', fillcolor='rgba(255,255,255,0.05)'))
        
        fig.update_layout(
            xaxis_rangeslider_visible=False, 
            height=450, 
            template="plotly_dark", 
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")

@st.fragment(run_every="1s")
def render_top_metrics():
    krw_price = pyupbit.get_current_price("KRW-BTC")
    fng_value, fng_class = get_fear_and_greed()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("현재 비트코인 (KRW 기준)", f"₩{krw_price:,.0f}" if krw_price else "로딩중...")
    col2.metric("공포/탐욕 지수", f"{fng_value} ({fng_class})")
    
    from datetime import timezone, timedelta
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    formatted_time = now.strftime(f"%Y-%m-%d ({weekdays[now.weekday()]}) %H:%M:%S")
    col3.metric("최신 업데이트", formatted_time)

def main():
    st.title("🚀 실시간 비트코인 정밀 타이밍 & 자산 앱")
    st.markdown("사용자가 선택한 타임프레임(분/시간/일/주)에 맞춰 AI가 **맞춤형 투자 시그널**을 정밀 분석합니다.")
    
    # 상단 메트릭스 실시간 업데이트
    render_top_metrics()
    
    st.markdown("---")
    
    # 사이드바 (내 계좌 연동만 유지)
    with st.sidebar:
        st.header("🔐 내 계좌 연동")
        access_key = st.text_input("Access Key", value="Pqb2kah8kT1hrQXYF6ELxg4Wezt5tXaeRwlLx53N", type="password")
        secret_key = st.text_input("Secret Key", type="password")
        
        if access_key and secret_key:
            try:
                upbit_client = pyupbit.Upbit(access_key, secret_key)
                krw_balance = upbit_client.get_balance("KRW")
                btc_balance = upbit_client.get_balance("KRW-BTC")
                if krw_balance is not None:
                    st.success("✅ 연동 완료")
                    st.metric("보유 원화", f"₩{krw_balance:,.0f}")
                    st.metric("보유 BTC", f"{btc_balance:.6f} BTC")
            except:
                pass
                
    # ---------------- 메인 레이아웃 ----------------
    left_col, right_col = st.columns([2.5, 1])
    
    with left_col:
        # 타임프레임 선택 라디오 버튼 (그래프와 겹치지 않게 메인 뷰 상단에 가로로 배치)
        interval_options = {
            "1분봉": "minute1",
            "3분봉": "minute3",
            "15분봉": "minute15",
            "1시간봉": "minute60",
            "4시간봉": "minute240",
            "일봉": "day",
            "주봉": "week",
            "월봉": "month"
        }
        
        selected_interval_name = st.radio(
            "⏱️ 타임프레임 선택",
            list(interval_options.keys()),
            index=4,
            horizontal=True
        )
        selected_interval_val = interval_options[selected_interval_name]
        
        # 선택한 타임프레임에 맞춰 실시간 차트와 시그널을 분석하는 조각 실행
        render_realtime_chart(selected_interval_val, selected_interval_name)

    with right_col:
        st.header("📋 실시간 호가창")
        render_realtime_orderbook()

if __name__ == "__main__":
    main()
