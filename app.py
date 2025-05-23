import os
from flask import Flask, render_template_string, request, Response
from functools import wraps
import yfinance as yf
import pandas_ta as ta
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import requests

app = Flask(__name__)

# توکن و چت آیدی تلگرام شما
TELEGRAM_BOT_TOKEN = "7436090932:AAETY1oQqTvcK4yd9NJmcH0irPeXbIp_d1M"
TELEGRAM_CHAT_ID = "6198128738"  # رشته باشد

ADMINS = {"admin1"}
ADMIN_PASSWORD = "123456"

def check_auth(username, password):
    return username == "admin" and password == ADMIN_PASSWORD

def authenticate():
    return Response('لطفا وارد شوید.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except Exception as e:
        print("خطا در ارسال پیام تلگرام:", e)
        return False

HTML_TEMPLATE = '''
<!doctype html>
<html><head><meta charset="UTF-8"><title>تحلیل تکنیکال</title></head>
<body style="font-family:Tahoma; direction:rtl; padding:20px">
  <h2>تحلیل بازار</h2>
  <form method="get">
    نام کاربری: <input name="username" value="{{username}}" required>
    <br><br>
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

def predict_price_movement(data):
    df = data.copy().dropna().tail(500)
    if len(df) < 100:
        return "داده کافی نیست"
    df['target'] = df['Close'].shift(-1) > df['Close']
    features = ['RSI', 'MACD', 'EMA_50', 'EMA_200', 'BB_upper', 'BB_lower', 'Stoch_K']
    X = df[features]
    y = df['target'].astype(int)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    model = LogisticRegression()
    model.fit(X_train, y_train)
    latest_features = X_scaled[-1].reshape(1, -1)
    prob_up = model.predict_proba(latest_features)[0][1]
    return round(prob_up * 100, 2)

def analyze(symbol="BTC-USD", interval="1h", lookback_days=30):
    data = yf.download(symbol, period=f"{lookback_days}d", interval=interval)
    if data.empty or len(data) < 50:
        return {"error": "داده کافی نیست."}
    data['RSI'] = ta.rsi(data['Close'], length=14)
    data['MACD'] = ta.macd(data['Close'])['MACD_12_26_9']
    data['EMA_50'] = ta.ema(data['Close'], length=50)
    data['EMA_200'] = ta.ema(data['Close'], length=200)
    bb = ta.bbands(data['Close'], length=20)
    data['BB_upper'] = bb['BBU_20_2.0']
    data['BB_lower'] = bb['BBL_20_2.0']
    stoch = ta.stoch(data['High'], data['Low'], data['Close'])
    data['Stoch_K'] = stoch['STOCHk_14_3_3']
    latest = data.iloc[-1]
    suggestion = []
    if latest['RSI'] < 30: suggestion.append("RSI: سیگنال خرید")
    elif latest['RSI'] > 70: suggestion.append("RSI: سیگنال فروش")
    if latest['EMA_50'] > latest['EMA_200']: suggestion.append("EMA کراس: روند صعودی")
    else: suggestion.append("EMA کراس: روند نزولی")
    if latest['Close'] < latest['BB_lower']: suggestion.append("قیمت زیر باند پایین بولینگر")
    elif latest['Close'] > latest['BB_upper']: suggestion.append("قیمت بالای باند بالا بولینگر")
    if latest['Stoch_K'] < 20: suggestion.append("Stochastic: اشباع فروش")
    elif latest['Stoch_K'] > 80: suggestion.append("Stochastic: اشباع خرید")
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
    send_telegram_message(message)

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

@app.route('/', methods=['GET'])
def home():
    username = request.args.get("username", "").strip()
    symbol = request.args.get("symbol", "BTC-USD")
    interval = request.args.get("interval", "1h")
    if username not in ADMINS:
        return "<h3>شما اجازه دسترسی ندارید. لطفا با ادمین تماس بگیرید.</h3>"
    result = analyze(symbol, interval)
    return render_template_string(HTML_TEMPLATE, result=result, symbol=symbol, interval=interval, username=username)

@app.route('/admin', methods=['GET', 'POST'])
@requires_auth
def admin_panel():
    message = ""
    if request.method == 'POST':
        action = request.form.get("action")
        user = request.form.get("username", "").strip()
        if action == "add":
            if user and user not in ADMINS:
                ADMINS.add(user)
                message = f"ادمین '{user}' اضافه شد."
            else:
                message = "نام کاربری معتبر نیست یا قبلا اضافه شده."
        elif action == "remove":
            if user in ADMINS:
                ADMINS.remove(user)
                message = f"ادمین '{user}' حذف شد."
            else:
                message = "کاربر در لیست ادمین‌ها نیست."
    admins_list = sorted(list(ADMINS))
    return render_template_string('''
    <h2>پنل مدیریت</h2>
    <p style="color:green;">{{message}}</p>
    <h3>ادمین‌های فعلی:</h3>
    <ul>{% for admin in admins %}<li>{{admin}}</li>{% endfor %}</ul>
    <hr>
    <form method="post">
      <input name="username" placeholder="نام کاربری ادمین">
      <button name="action" value="add" type="submit">اضافه کردن</button>
      <button name="action" value="remove" type="submit">حذف کردن</button>
    </form><br><a href="/">بازگشت</a>
    ''', admins=admins_list, message=message)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host="0.0.0.0", port=port)
