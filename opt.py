import os
import requests
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from fastapi import FastAPI

# ==============================
# متغيرات البيئة
# ==============================
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

app = FastAPI()

UNDERLYING = "AAPL"  # يمكنك إضافة أكثر من سهم لاحقًا

# ==============================
# دالة لجلب عقود الخيارات مع التفاصيل الدقيقة
# ==============================
def fetch_options_report():
    today = date.today()
    contracts_url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": UNDERLYING,
        "limit": 5,  # عدد العقود
        "apiKey": POLYGON_API_KEY
    }

    contracts = requests.get(contracts_url, params=params).json()
    report_lines = []

    for option in contracts.get("results", []):

        ticker = option["ticker"]
        strike = option["strike_price"]
        expiry = option["expiration_date"]
        ctype = option["contract_type"]

        agg_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{today}/{today}"
        agg_params = {"apiKey": POLYGON_API_KEY}
        agg = requests.get(agg_url, params=agg_params).json()

        if "results" in agg:
            data = agg["results"][0]
            premium = data["c"] * data["v"] * 100
            line = f"""
🔥 {UNDERLYING} Options Report

Ticker: {ticker}
Type: {ctype.upper()}
Strike: {strike}
Expiry: {expiry}
Open: {data['o']}
High: {data['h']}
Low: {data['l']}
Close: {data['c']}
Volume: {data['v']}
Trades: {data['n']}
VWAP: {data['vw']}
Premium: ${premium:,.2f}
"""
            report_lines.append(line)

    return "\n".join(report_lines)

# ==============================
# دالة إرسال التقرير إلى التلجرام
# ==============================
def send_report_to_telegram():
    report = fetch_options_report()
    if report:
        # إرسال الرسالة: لاحقاً يمكن تعديل bot.send_message لتوجيهها للقناة مباشرة
        # مثال: bot.send_message(chat_id="@اسم_القناة", text=report)
        print(report)  # مؤقتًا نطبع التقرير في الكونسول
    else:
        print("No data to send ❌")

# ==============================
# جدولة الإرسال كل 5 دقائق
# ==============================
scheduler = BackgroundScheduler()
scheduler.add_job(send_report_to_telegram, 'interval', minutes=5)
scheduler.start()

# ==============================
# FastAPI Route للتحقق من حالة البوت
# ==============================
@app.get("/")
def home():
    return {"status": "Options Alert Bot is running"}

# ==============================
# تشغيل FastAPI
# ==============================
if __name__ == "__main__":
    import uvicorn
    print("Starting Options Alert Bot...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
