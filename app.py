import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="비트코인 매수/매도 타이밍 AI 분석기", layout="wide")

@st.cache_data(ttl=3600)
def get_crypto_data():
    """야후 파이낸스에서 비트코인 일봉 데이터를 가져옵니다."""
    try:
        btc = yf.download("BTC-USD", period="6mo", interval="1d", progress=False)
        return btc
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_fear_and_greed():
    """Alternative.me에서 공포/탐욕 지수를 가져옵니다."""
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1")
        data = response.json()
        return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except:
        return 50, "Unknown"

def get_upbit_ticker():
    """업비트에서 실시간 원화(KRW) 비트코인 가격을 가져옵니다."""
    try:
        url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        data = response.json()[0]
        return data['trade_price'], data['signed_change_rate']
    except:
        return 0, 0

def get_upbit_orderbook():
    """업비트에서 실시간 매도/매수 호가창(Orderbook) 데이터를 가져옵니다."""
    try:
        url = "https://api.upbit.com/v1/orderbook?markets=KRW-BTC"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)
        return response.json()[0]['orderbook_units']
    except:
        return []

def calculate_rsi(data, periods=14):
    """RSI(상대강도지수)를 계산합니다."""
    if isinstance(data.columns, pd.MultiIndex):
        close_series = data['Close'].iloc[:, 0]
    else:
        close_series = data['Close']
        
    close_delta = close_series.diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    rsi = ma_up / ma_down
    return 100 - (100 / (1 + rsi))

@st.fragment(run_every="1s")
def render_realtime_orderbook():
    """1초마다 자동으로 실행되어 호가창을 실시간 업데이트하는 조각(Fragment)"""
    # 업비트 실시간 가격 및 호가 데이터 호출
    krw_price, change_rate = get_upbit_ticker()
    orderbook = get_upbit_orderbook()
    
    # 상단에 현재가 다시 표시 (실시간 강조)
    st.markdown(f"### ⚡ 현재가: <span style='color:#00cc96;'>₩{krw_price:,.0f}</span> ({change_rate*100:.2f}%)", unsafe_allow_html=True)
    
    if orderbook:
        st.markdown("**(단위: KRW / BTC)**")
        
        # 매도 호가 (Ask) - 높은 가격이 위로
        for unit in reversed(orderbook[:10]):
            ask_price = unit['ask_price']
            ask_size = unit['ask_size']
            st.markdown(f"<div style='background-color:rgba(255, 75, 75, 0.2); padding:5px; border-radius:5px; margin-bottom:2px; display:flex; justify-content:space-between;'>"
                        f"<span style='color:#ff4b4b; font-weight:bold;'>{ask_price:,.0f}</span>"
                        f"<span>{ask_size:.4f}</span>"
                        f"</div>", unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 10px 0; border-color: gray;'>", unsafe_allow_html=True)
        
        # 매수 호가 (Bid) - 높은 가격이 위로
        for unit in orderbook[:10]:
            bid_price = unit['bid_price']
            bid_size = unit['bid_size']
            st.markdown(f"<div style='background-color:rgba(0, 204, 150, 0.2); padding:5px; border-radius:5px; margin-bottom:2px; display:flex; justify-content:space-between;'>"
                        f"<span style='color:#00cc96; font-weight:bold;'>{bid_price:,.0f}</span>"
                        f"<span>{bid_size:.4f}</span>"
                        f"</div>", unsafe_allow_html=True)
    else:
        st.warning("호가창 데이터를 불러올 수 없습니다.")
        
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')}")

def main():
    st.title("🚀 실시간 비트코인 원화(KRW) 매수/매도 타이밍 앱")
    st.markdown("`Upbit` 실시간 원화 가격 및 호가창, `Yahoo Finance` 차트, `Alternative.me` 지수를 종합 분석합니다.")
    
    with st.spinner('초기 데이터를 불러오는 중입니다...'):
        df = get_crypto_data()
        fng_value, fng_class = get_fear_and_greed()
    
    if df.empty:
        st.error("데이터를 불러오지 못했습니다.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        close_series = df['Close'].iloc[:, 0]
        open_series = df['Open'].iloc[:, 0]
        high_series = df['High'].iloc[:, 0]
        low_series = df['Low'].iloc[:, 0]
    else:
        close_series = df['Close']
        open_series = df['Open']
        high_series = df['High']
        low_series = df['Low']

    df['EMA20'] = close_series.ewm(span=20, adjust=False).mean()
    df['EMA50'] = close_series.ewm(span=50, adjust=False).mean()
    df['RSI'] = calculate_rsi(df)
    
    usd_price = float(close_series.iloc[-1])
    current_rsi = float(df['RSI'].iloc[-1])
    current_ema20 = float(df['EMA20'].iloc[-1])
    
    # ---------------- UI 구성 ----------------
    col1, col2, col3 = st.columns(3)
    col1.metric("현재 비트코인 (USD 기준)", f"${usd_price:,.2f}")
    col2.metric("RSI (14일)", f"{current_rsi:.2f}")
    col3.metric("공포/탐욕 지수", f"{fng_value} ({fng_class})")
    
    # ---------------- 2단 레이아웃 (시그널 & 호가창) ----------------
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.header("🤖 AI 투자 시그널")
        
        signal = "관망 (Hold)"
        color = "gray"
        reason = []
        
        if current_rsi > 70 and fng_value >= 75:
            signal = "🚨 강력 매도 / 차익 실현 (Sell)"
            color = "#ff4b4b" 
            reason.append("RSI가 70을 초과한 '과매수' 상태입니다.")
            reason.append("시장이 '극단적 탐욕' 상태이므로 단기 조정 가능성이 높습니다.")
        elif current_rsi < 30 and fng_value <= 25:
            signal = "💰 강력 매수 기회 (Buy)"
            color = "#00cc96" 
            reason.append("RSI가 30 미만인 '과매도' 상태입니다.")
            reason.append("시장이 '극단적 공포' 상태로 저점 매수 기회일 수 있습니다.")
        elif usd_price > current_ema20:
            signal = "📈 단기 상승 추세 - 분할 매수 / 홀딩"
            color = "#ffa15a" 
            reason.append("가격이 20일 이동평균선 위에 위치해 단기 상승 추세가 유지되고 있습니다.")
            if current_rsi > 60:
                reason.append("다만 RSI가 높은 편이므로 적극적인 추격 매수보다는 홀딩을 권장합니다.")
            else:
                reason.append("분할 매수를 고려해볼 수 있는 구간입니다.")
        else:
            signal = "📉 단기 하락 추세 - 관망"
            color = "#636efa" 
            reason.append("가격이 20일 이동평균선 아래에 있어 하락 채널에 있습니다. 관망하는 것이 좋습니다.")
            
        st.markdown(f"<h2 style='color: {color};'>{signal}</h2>", unsafe_allow_html=True)
        
        st.subheader("💡 판단 근거")
        for r in reason:
            st.write(f"- {r}")

        st.subheader("📊 비트코인 일봉 차트 (USD 기준)")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index,
                    open=open_series, high=high_series,
                    low=low_series, close=close_series, 
                    increasing_line_color='#ff4b4b', decreasing_line_color='#636efa',
                    name='BTC/USD'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='orange', width=1.5), name='EMA 20 (단기)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color='blue', width=1.5), name='EMA 50 (중기)'))
        fig.update_layout(xaxis_rangeslider_visible=False, height=400, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.header("📋 실시간 호가창")
        # 여기서 1초마다 자동 새로고침되는 함수를 호출합니다!
        render_realtime_orderbook()

if __name__ == "__main__":
    main()
