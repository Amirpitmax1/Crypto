import os
from flask import Flask
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = "7540066547:AAGRbv2Wpf0-btwV_eB9OsCS0tYXkxEWt6U"
CHANNEL_ID = "-1002548463351"

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def ema(series, period=20):
    return series.ewm(span=period, adjust=False).mean()

def analyze(symbol="BTC-USD", interval="1h"):
    try:
        df = yf.download(symbol, period="5d", interval=interval)
        if df.empty or len(df) < 30:
            return "📉 داده کافی برای تحلیل وجود ندارد."
        df['RSI'] = rsi(df['Close'])
        df['EMA20'] = ema(df['Close'])

        latest = df.dropna().iloc[-1]
        msg = (
            f"📊 تحلیل {symbol} ({interval})\n"
            f"💰 قیمت: {latest['Close']:.2f}\n"
            f"📈 RSI: {latest['RSI']:.2f}\n"
            f"📊 EMA20: {latest['EMA20']:.2f}\n"
            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        return msg
    except Exception as e:
        print("تحلیل شکست خورد:", e)
        return "❌ خطا در تحلیل"

@app.route('/')
def home():
    result = analyze()
    send_to_telegram(result)
    return result

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
