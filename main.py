import os
import requests
from datetime import date
import asyncio
from fastapi import FastAPI
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

# ==============================
# FastAPI
# ==============================
app = FastAPI()

@app.get("/")
def home():
    return {"status": "Options Alert Bot is running"}

# ==============================
# الأسهم المراد مراقبتها
# ==============================
STOCKS = ["AAPL", "MSFT"]  # يمكن إضافة المزيد لاحقًا

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

    # تقسيم الرسائل الطويلة (>4096 حرف)
    for chunk in [full_report[i:i+4000] for i in range(0, len(full_report), 4000)]:
        await context.bot.send_message(chat_id=chat_id, text=chunk)
    print(f"Report sent to chat {chat_id} ✅")

# ==============================
# أوامر البوت
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("✅ You are now subscribed to Options Reports every 5 minutes.")

    # إرسال تقرير فوري عند الاشتراك
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
# الدالة الرئيسية لتشغيل FastAPI + Telegram Bot
# ==============================
async def main():
    # إعداد البوت
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))

    # تشغيل البوت
    await application.initialize()
    await application.start()
    print("🚀 Telegram Bot is running...")

    # تشغيل FastAPI
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
    server = uvicorn.Server(config)

    # تشغيل كلاهما في نفس الحدث
    await asyncio.gather(server.serve(), application.updater.start_polling())

# ==============================
# تشغيل التطبيق
# ==============================
if __name__ == "__main__":
    asyncio.run(main())
