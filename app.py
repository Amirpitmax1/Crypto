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

# --- تنظیمات تلگرام ---
TELEGRAM_BOT_TOKEN = "7436090932:AAETY1oQqTvcK4yd9NJmcH0irPeXbIp_d1M"
CHANNEL_ID = "-1002548463351"  # آیدی کانال تلگرام (با -100 شروع شود)
ADMIN_CHAT_ID = "6198128738"  # آیدی چت مدیر برای پاسخ به /start

# ارسال پیام به تلگرام
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text})
        if response.status_code != 200:
            print(f"❌ خطا در ارسال پیام تلگرام: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print("❌ خطا در ارسال پیام:", e)
        return False

# پیش‌بینی حرکت قیمت با 5 اندیکاتور مهم
def predict_price_movement(data):
    try:
        df = data.copy().dropna().tail(500)
        if len(df) < 100:
            return "داده کافی نیست برای AI"
        df['target'] = df['Close'].shift(-1) > df['Close']
        features = ['RSI', 'MACD', 'EMA_50', 'EMA_200', 'BB_upper']
        for f in features:
            if f not in df.columns:
                return f"ستون {f} موجود نیست"
        X = df[features]
        y = df['target'].astype(int)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
        model = LogisticRegression(max_iter=1000)
        model.fit(X_train, y_train)
        latest_features = X_scaled[-1].reshape(1, -1)
        prob_up = model.predict_proba(latest_features)[0][1]
        return round(prob_up * 100, 2)
    except Exception as e:
        print("❌ خطا در پیش‌بینی AI:", e)
        return "خطا در پیش‌بینی AI"

# تحلیل داده‌ها با 5 اندیکاتور
def analyze(symbol="BTC-USD", interval="1h", lookback_days=30):
    try:
        data = yf.download(symbol, period=f"{lookback_days}d", interval=interval)
        if data.empty or len(data) < 50:
            msg = "⚠️ داده کافی نیست."
            send_telegram_message(CHANNEL_ID, msg)
            return {"error": msg}

        data['RSI'] = ta.rsi(data['Close'], length=14)
        macd = ta.macd(data['Close'])
        if macd is None or macd.empty:
            msg = "⚠️ خطا در محاسبه MACD."
            send_telegram_message(CHANNEL_ID, msg)
            return {"error": msg}
        data['MACD'] = macd['MACD_12_26_9']
        data['EMA_50'] = ta.ema(data['Close'], length=50)
        data['EMA_200'] = ta.ema(data['Close'], length=200)
        bb = ta.bbands(data['Close'], length=20)
        if bb is None or bb.empty:
            msg = "⚠️ خطا در محاسبه بولینگر."
            send_telegram_message(CHANNEL_ID, msg)
            return {"error": msg}
        data['BB_upper'] = bb['BBU_20_2.0']
        data['BB_lower'] = bb['BBL_20_2.0']

        data_clean = data.dropna(subset=['RSI', 'MACD', 'EMA_50', 'EMA_200', 'BB_upper', 'BB_lower'])
        if data_clean.empty:
            msg = "⚠️ داده کافی پس از حذف مقادیر نال نیست."
            send_telegram_message(CHANNEL_ID, msg)
            return {"error": msg}

        latest = data_clean.iloc[-1]

        suggestion = []
        if latest['RSI'] < 30:
            suggestion.append("RSI: سیگنال خرید")
        elif latest['RSI'] > 70:
            suggestion.append("RSI: سیگنال فروش")

        if latest['EMA_50'] > latest['EMA_200']:
            suggestion.append("EMA کراس: روند صعودی")
        else:
            suggestion.append("EMA کراس: روند نزولی")

        if latest['Close'] < latest['BB_lower']:
            suggestion.append("قیمت زیر باند پایین بولینگر")
        elif latest['Close'] > latest['BB_upper']:
            suggestion.append("قیمت بالای باند بالا بولینگر")

        ai_prediction = predict_price_movement(data_clean)

        message = (
            f"📊 تحلیل {symbol} ({interval}):\n"
            f"💰 قیمت: {round(latest['Close'], 2)}\n"
            f"RSI: {round(latest['RSI'], 2)}\n"
            f"MACD: {round(latest['MACD'], 2)}\n"
            f"EMA50: {round(latest['EMA_50'], 2)} | EMA200: {round(latest['EMA_200'], 2)}\n"
            f"AI: {ai_prediction}% احتمال رشد\n"
            f"🕓 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        send_telegram_message(CHANNEL_ID, message)

        return {
            "symbol": symbol,
            "interval": interval,
            "price": round(latest['Close'], 2),
            "RSI": round(latest['RSI'], 2),
            "MACD": round(latest['MACD'], 2),
            "EMA_50": round(latest['EMA_50'], 2),
            "EMA_200": round(latest['EMA_200'], 2),
            "BB_upper": round(latest['BB_upper'], 2),
            "BB_lower": round(latest['BB_lower'], 2),
            "suggestion": suggestion,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "AI_Prediction": f"{ai_prediction}% احتمال رشد در کندل بعدی"
        }
    except Exception as e:
        error_msg = f"❌ خطا در آنالیز: {e}"
        print(error_msg)
        send_telegram_message(CHANNEL_ID, error_msg)
        return {"error": "خطا در تحلیل داده‌ها"}

# وب‌هوک تلگرام
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data:
        return "nok", 400
    if "message" in data:
        msg = data["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")
        if text == "/start":
            reply = "سلام! ربات تحلیل فعال است. برای مشاهده تحلیل به وب‌سایت مراجعه کنید."
            send_telegram_message(chat_id, reply)
        else:
            send_telegram_message(chat_id, "فقط دستور /start پشتیبانی می‌شود.")
    return "ok"

# صفحه وب اصلی
@app.route('/', methods=['GET'])
def home():
    symbol = request.args.get("symbol", "BTC-USD")
    interval = request.args.get("interval", "1h")
    result = analyze(symbol, interval)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4000))
    app.run(host="0.0.0.0", port=port)
