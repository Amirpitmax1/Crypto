import os
from flask import Flask, request, jsonify
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import requests

app = Flask(__name__)

# اطلاعات تلگرام (می‌توانید با اطلاعات خودتان جایگزین کنید)
TELEGRAM_BOT_TOKEN = "7436090932:AAETY1oQqTvcK4yd9NJmcH0irPeXbIp_d1M"
CHANNEL_ID = "-1002548463351"

# ارسال پیام به تلگرام
def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, data={"chat_id": chat_id, "text": text})
        return response.status_code == 200
    except Exception as e:
        print("خطا در ارسال پیام:", e)
        return False

# تحلیل اصلی
def analyze(symbol="BTC-USD", interval="1h", lookback_days=15):
    try:
        df = yf.download(symbol, period=f"{lookback_days}d", interval=interval)
        if df.empty or len(df) < 100:
            return {"error": "❌ داده کافی برای تحلیل وجود ندارد."}

        # اندیکاتورها
        df["RSI"] = ta.rsi(df["Close"])
        df["EMA_50"] = ta.ema(df["Close"], length=50)
        df["EMA_200"] = ta.ema(df["Close"], length=200)
        macd = ta.macd(df["Close"])
        df["MACD"] = macd["MACD_12_26_9"]
        bb = ta.bbands(df["Close"], length=20)
        df["BBU"] = bb["BBU_20_2.0"]
        df["BBL"] = bb["BBL_20_2.0"]

        df.dropna(inplace=True)
        if df.empty:
            return {"error": "❌ اندیکاتورها داده کافی تولید نکردند."}

        latest = df.iloc[-1]
        suggestions = []

        if latest["RSI"] < 30:
            suggestions.append("🔹 RSI زیر ۳۰: سیگنال خرید")
        elif latest["RSI"] > 70:
            suggestions.append("🔻 RSI بالای ۷۰: سیگنال فروش")

        if latest["EMA_50"] > latest["EMA_200"]:
            suggestions.append("📈 EMA کراس صعودی")
        else:
            suggestions.append("📉 EMA کراس نزولی")

        if latest["Close"] < latest["BBL"]:
            suggestions.append("💰 قیمت زیر باند بولینگر: احتمالا برگشت")
        elif latest["Close"] > latest["BBU"]:
            suggestions.append("⚠️ قیمت بالای باند بولینگر: احتیاط")

        # پیش‌بینی هوش مصنوعی ساده
        df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)
        features = ["RSI", "EMA_50", "EMA_200", "MACD", "BBU"]
        X = df[features]
        y = df["Target"]

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = LogisticRegression(max_iter=1000)
        model.fit(X_scaled[:-1], y[:-1])
        prob = model.predict_proba([X_scaled[-1]])[0][1]
        ai_prediction = round(prob * 100, 2)

        message = (
            f"📊 تحلیل {symbol}:\n"
            f"💵 قیمت: {round(latest['Close'], 2)}\n"
            f"📌 RSI: {round(latest['RSI'], 2)} | MACD: {round(latest['MACD'], 2)}\n"
            f"📌 EMA50: {round(latest['EMA_50'], 2)} | EMA200: {round(latest['EMA_200'], 2)}\n"
            f"🤖 AI: {ai_prediction}% احتمال رشد\n"
            + "\n".join(suggestions) +
            f"\n🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        send_telegram_message(CHANNEL_ID, message)

        return {
            "symbol": symbol,
            "interval": interval,
            "price": round(latest["Close"], 2),
            "RSI": round(latest["RSI"], 2),
            "EMA_50": round(latest["EMA_50"], 2),
            "EMA_200": round(latest["EMA_200"], 2),
            "MACD": round(latest["MACD"], 2),
            "BBU": round(latest["BBU"], 2),
            "BBL": round(latest["BBL"], 2),
            "AI_Prediction": f"{ai_prediction}%",
            "Suggestions": suggestions
        }

    except Exception as e:
        print("❌ خطای تحلیل:", e)
        return {"error": "❌ خطا در تحلیل داده‌ها."}

# وب‌سایت اصلی
@app.route("/")
def home():
    symbol = request.args.get("symbol", "BTC-USD")
    interval = request.args.get("interval", "1h")
    result = analyze(symbol, interval)
    return jsonify(result)

# اجرا
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
