import os
import requests
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext, JobQueue
from fastapi import FastAPI
import threading

# ==============================
# متغيرات البيئة
# ==============================
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
app = FastAPI()

UNDERLYING = "AAPL"  # يمكنك إضافة أكثر من سهم لاحقًا

# ==============================
# دالة لجلب تقرير عقود الخيارات
# ==============================
def fetch_options_report():
    today = date.today()
    contracts_url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {
        "underlying_ticker": UNDERLYING,
        "limit": 5,
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

    return "\n".join(report_lines) if report_lines else "No trading data today."

# ==============================
# دالة لإرسال التقرير للمستخدم
# ==============================
def send_report(context: CallbackContext):
    chat_id = context.job.context
    report = fetch_options_report()
    context.bot.send_message(chat_id=chat_id, text=report)
    print(f"Report sent to chat {chat_id} ✅")

# ==============================
# أوامر البوت
# ==============================
def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    update.message.reply_text("✅ You are now subscribed to Options Reports every 5 minutes.")

    # إضافة مهمة إرسال التقارير كل 5 دقائق
    context.job_queue.run_repeating(send_report, interval=300, first=0, context=chat_id, name=str(chat_id))

def stop(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in jobs:
        job.schedule_removal()
    update.message.reply_text("🛑 You have unsubscribed from Options Reports.")

# ==============================
# تشغيل بوت Telegram في Thread منفصل
# ==============================
def start_telegram_bot():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("stop", stop))

    print("🚀 Options Telegram Bot is running...")
    updater.start_polling()
    updater.idle()

# ==============================
# FastAPI Route للتحقق من حالة البوت
# ==============================
@app.get("/")
def home():
    return {"status": "Options Alert Bot is running"}

# ==============================
# تشغيل FastAPI و Telegram معًا
# ==============================
if __name__ == "__main__":
    import uvicorn
    # تشغيل البوت في Thread منفصل
    threading.Thread(target=start_telegram_bot, daemon=True).start()
    # تشغيل FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
