import os
from flask import Flask, request
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
import requests

app = Flask(__name__)

# توکن و آیدی کانال تلگرام
BOT_TOKEN = "7540066547:AAGRbv2Wpf0-btwV_eB9OsCS0tYXkxEWt6U"
CHANNEL_ID = "-1002548463351"

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": text}
    try:
        r = requests.post(url, data=data)
        print("Telegram response:", r.text)
    except Exception as e:
        print("❌ Telegram error:", e)

def analyze(symbol="BTC-USD", interval="1h"):
    try:
        df = yf.download(symbol, period="5d", interval=interval)
        if df.empty or len(df) < 30:
            return "📉 داده کافی برای تحلیل وجود ندارد."

        df['RSI'] = ta.rsi(df['Close'])
        df['EMA20'] = ta.ema(df['Close'], length=20)

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
        print("❌ تحلیل شکست خورد:", e)
        return "❌ خطا در تحلیل"

@app.route('/')
def home():
    result = analyze()
    send_to_telegram(result)
    return result

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
