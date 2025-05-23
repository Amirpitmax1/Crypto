import os
from flask import Flask, request, render_template_string
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "7436090932:AAETY1oQqTvcK4yd9NJmcH0irPeXbIp_d1M"
ADMIN_CHAT_ID = "6198128738"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text})
        if response.status_code != 200:
            print(f"خطا در ارسال پیام تلگرام: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print("خطا در ارسال پیام:", e)
        return False

def predict_price_movement(data):
    try:
        df = data.copy().dropna().tail(500)
        if len(df) < 100:
            return "داده کافی نیست"
        df['target'] = df['Close'].shift(-1) > df['Close']
        features = ['RSI', 'MACD', 'EMA_50', 'EMA_200', 'BB_upper', 'BB_lower', 'Stoch_K']

        # چک وجود همه ستون‌ها
        for f in features:
            if f not in df.columns:
                return "ستون {} موجود نیست".format(f)

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
        print("خطا در پیش‌بینی AI:", e)
        return "خطا در پیش‌بینی"

def analyze(symbol="BTC-USD", interval="1h", lookback_days=30):
    try:
        data = yf.download(symbol, period=f"{lookback_days}d", interval=interval)
        if data.empty or len(data) < 50:
            return {"error": "داده کافی نیست."}

        # محاسبه اندیکاتورها با چک خطا
        data['RSI'] = ta.rsi(data['Close'], length=14)
        macd_df = ta.macd(data['Close'])
        if macd_df is None or 'MACD_12_26_9' not in macd_df.columns:
            return {"error": "خطا در محاسبه MACD"}
        data['MACD'] = macd_df['MACD_12_26_9']

        data['EMA_50'] = ta.ema(data['Close'], length=50)
        data['EMA_200'] = ta.ema(data['Close'], length=200)

        bb = ta.bbands(data['Close'], length=20)
        if bb is None or 'BBU_20_2.0' not in bb.columns or 'BBL_20_2.0' not in bb.columns:
            return {"error": "خطا در محاسبه باند بولینگر"}
        data['BB_upper'] = bb['BBU_20_2.0']
        data['BB_lower'] = bb['BBL_20_2.0']

        stoch = ta.stoch(data['High'], data['Low'], data['Close'])
        if stoch is None or 'STOCHk_14_3_3' not in stoch.columns:
            return {"error": "خطا در محاسبه Stochastic"}
        data['Stoch_K'] = stoch['STOCHk_14_3_3']

        latest = data.iloc[-1]

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

        if latest['Stoch_K'] < 20:
            suggestion.append("Stochastic: اشباع فروش")
        elif latest['Stoch_K'] > 80:
            suggestion.append("Stochastic: اشباع خرید")

        ai_prediction = predict_price_movement(data)

        message = (
            f"تحلیل {symbol} در تایم‌فریم {interval}:\n"
            f"قیمت: {round(latest['Close'], 2)}\n"
            f"RSI: {round(latest['RSI'], 2)}\n"
            f"MACD: {round(latest['MACD'], 2)}\n"
            f"EMA 50: {round(latest['EMA_50'], 2)}\n"
            f"EMA 200: {round(latest['EMA_200'], 2)}\n"
            f"پیش‌بینی رشد: {ai_prediction}%\n"
            f"زمان: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        send_telegram_message(ADMIN_CHAT_ID, message)

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
            "Stoch_K": round(latest['Stoch_K'], 2),
            "suggestion": suggestion,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "AI_Prediction": f"{ai_prediction}% احتمال رشد در کندل بعدی"
        }
    except Exception as e:
        print("خطا در آنالیز داده‌ها:", e)
        return {"error": "خطا در آنالیز داده‌ها"}

HTML_TEMPLATE = '''
<!doctype html>
<html><head><meta charset="UTF-8"><title>تحلیل تکنیکال</title></head>
<body style="font-family:Tahoma; direction:rtl; padding:20px">
  <h2>تحلیل بازار</h2>
  <form method="get">
    نماد: <input name="symbol" value="{{symbol}}" required>
    تایم‌فریم: 
    <select name="interval">
      <option value="1m" {% if interval=="1m" %}selected{% endif %}>1 دقیقه</option>
      <option value="5m" {% if interval=="5m" %}selected{% endif %}>5 دقیقه</option>
      <option value="15m" {% if interval=="15m" %}selected{% endif %}>15 دقیقه</option>
      <option value="1h" {% if interval=="1h" %}selected{% endif %}>1 ساعت</option>
      <option value="4h" {% if interval=="4h" %}selected{% endif %}>4 ساعت</option>
      <option value="1d" {% if interval=="1d" %}selected{% endif %}>1 روز</option>
    </select>
    <button type="submit">تحلیل کن</button>
  </form>
  {% if result and not result.error %}
    <h3>{{result.symbol}} - {{result.interval}} - قیمت: {{result.price}}</h3>
    <ul>
      <li>RSI: {{result.RSI}}</li>
      <li>MACD: {{result.MACD}}</li>
      <li>EMA 50: {{result.EMA_50}}</li>
      <li>EMA 200: {{result.EMA_200}}</li>
      <li>باند بولینگر: {{result.BB_lower}} - {{result.BB_upper}}</li>
      <li>Stochastic K: {{result.Stoch_K}}</li>
      <li><b>پیش‌بینی AI:</b> {{result.AI_Prediction}}</li>
    </ul>
    <b>پیشنهاد:</b>
    <ul>{% for s in result.suggestion %}<li>{{s}}</li>{% endfor %}</ul>
    <small>زمان: {{result.timestamp}}</small>
  {% elif result.error %}
    <p style="color:red">خطا: {{result.error}}</p>
  {% endif %}
</body></html>
'''

@app.route('/', methods=['GET'])
def home():
    symbol = request.args.get("symbol", "BTC-USD")
    interval = request.args.get("interval", "1h")
    result = analyze(symbol, interval)
    return render_template_string(HTML_TEMPLATE, result=result, symbol=symbol, interval=interval)

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
