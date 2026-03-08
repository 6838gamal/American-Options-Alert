import os
import requests
from datetime import date
from fastapi import FastAPI
import threading
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    JobQueue,
)

# ==============================
# متغيرات البيئة
# ==============================
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app = FastAPI()

# الأسهم المراد مراقبتها
STOCKS = ["AAPL", "MSFT"]  # يمكنك إضافة المزيد لاحقًا

# ==============================
# دالة لجلب تقرير عقود الخيارات
# ==============================
def fetch_options_report(underlying: str):
    today = date.today()
    contracts_url = "https://api.polygon.io/v3/reference/options/contracts"
    params = {"underlying_ticker": underlying, "limit": 5, "apiKey": POLYGON_API_KEY}

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
🔥 {underlying} Options Report

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

    return "\n".join(report_lines) if report_lines else f"No trading data today for {underlying}."

# ==============================
# دالة لإرسال التقرير للمستخدم
# ==============================
async def send_report(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id

    full_report = ""
    for stock in STOCKS:
        full_report += fetch_options_report(stock) + "\n" + ("-"*30) + "\n"

    # تقسيم الرسائل الطويلة
    for chunk in [full_report[i:i+4000] for i in range(0, len(full_report), 4000)]:
        await context.bot.send_message(chat_id=chat_id, text=chunk)
    print(f"Report sent to chat {chat_id} ✅")

# ==============================
# أوامر البوت
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("✅ You are now subscribed to Options Reports every 5 minutes.")

    # إرسال تقرير فوري
    full_report = ""
    for stock in STOCKS:
        full_report += fetch_options_report(stock) + "\n" + ("-"*30) + "\n"

    for chunk in [full_report[i:i+4000] for i in range(0, len(full_report), 4000)]:
        await context.bot.send_message(chat_id=chat_id, text=chunk)

    # إضافة مهمة إرسال التقارير كل 5 دقائق
    context.job_queue.run_repeating(send_report, interval=300, first=300, chat_id=chat_id)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs()
    for job in jobs:
        if job.chat_id == chat_id:
            job.schedule_removal()
    await update.message.reply_text("🛑 You have unsubscribed from Options Reports.")

# ==============================
# تشغيل بوت Telegram في Thread منفصل
# ==============================
def start_telegram_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stop", stop))

    print("🚀 Options Telegram Bot is running...")
    app_bot.run_polling()

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
