import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

# =========================
# ENV VARIABLES
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
PORT = int(os.getenv("PORT", 8080))   # Railway provides this

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# HELPERS
# =========================
def box(title: str, content: str) -> str:
    return f"🚀 *{title}*\n\n{content}"

# =========================
# COMMAND HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = box(
        "ALPHA BOT PREMIUM",
        "📊 /price BTC\n"
        "🔥 /pumpfun\n"
        "📈 /trending\n"
        "⚠️ /alert BTC\n"
        "💼 /portfolio 1000 1200\n"
        "🎯 /risk 1000 1200\n"
        "📰 /news"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (keep your existing price logic but make it async)
    # Just change update.message.reply_text → await update.message.reply_text
    # Same for all other commands
    try:
        symbol = context.args[0].upper() if context.args else "BTC"
        # Your CMC code here...
        # For now, placeholder:
        await update.message.reply_text(f"Price of {symbol} fetched (implement full logic)", parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("⚠️ Price fetch failed.")


# Add other commands similarly (pumpfun, alert, trending, portfolio, risk, news)
# Make them all async and use await for reply_text

# =========================
# MAIN
# =========================
def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is missing!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("price", price))
    # Add the rest: pumpfun, alert, trending, portfolio, risk, news

    # Webhook mode (best for Railway)
    logger.info(f"Starting bot with webhook on port {PORT}")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,                    # Secret path
        webhook_url=f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/{TELEGRAM_TOKEN}" if os.getenv('RAILWAY_PUBLIC_DOMAIN') else None,
    )


if __name__ == "__main__":
    main()
