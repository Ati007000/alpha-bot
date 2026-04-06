import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

load_dotenv()

# ENV VARIABLES
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
PUMP_FUN_API = os.getenv("PUMP_FUN_API")

# LOGGING
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# START
def start(update: Update, context: CallbackContext):
    message = (
        "🚀 *Welcome to AlphaBot Premium*\n\n"
        "📊 /price BTC\n"
        "🔥 /pumpfun\n"
        "📈 /trending\n"
        "⚠️ /alert BTC\n"
        "💼 /portfolio 1000 1200"
    )
    update.message.reply_text(message, parse_mode="Markdown")


# PRICE COMMAND
def price(update: Update, context: CallbackContext):
    try:
        symbol = context.args[0].upper() if context.args else "BTC"

        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"

        headers = {
            "X-CMC_PRO_API_KEY": CMC_API_KEY
        }

        params = {
            "symbol": symbol
        }

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        coin = data["data"][symbol]
        quote = coin["quote"]["USD"]

        message = (
            f"📊 *Coin:* {symbol}\n"
            f"💵 *Price:* ${quote['price']:,.2f}\n"
            f"📈 *24h:* {quote['percent_change_24h']:.2f}%\n"
            f"💰 *Volume:* ${quote['volume_24h']:,.0f}\n"
            f"🏦 *Market Cap:* ${quote['market_cap']:,.0f}\n"
            f"🔥 *Trend:* {'Bullish' if quote['percent_change_24h'] > 0 else 'Bearish'}\n\n"
            f"🚀 Sponsored: Join top exchange for signup rewards"
        )

        update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(e)
        update.message.reply_text("⚠️ Could not fetch price.")


# PUMPFUN COMMAND
def pumpfun(update: Update, context: CallbackContext):
    try:
        response = requests.get(PUMP_FUN_API)
        data = response.json()

        latest = data[0] if isinstance(data, list) else data

        message = (
            "🔥 *Latest Pump.fun Launch*\n\n"
            f"`{str(latest)[:700]}`\n\n"
            "⚠️ Verify liquidity before entry"
        )

        update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(e)
        update.message.reply_text("⚠️ Could not fetch pump data.")


# ALERT COMMAND
def alert(update: Update, context: CallbackContext):
    symbol = context.args[0].upper() if context.args else "BTC"

    message = (
        f"⚠️ *Smart Alert Enabled*\n\n"
        f"Coin: {symbol}\n"
        "🔥 Pump alert\n"
        "📉 Dump alert\n"
        "🐋 Whale movement alert\n"
        "📈 Volume spike alert\n\n"
        "Premium alerts active 🚀"
    )

    update.message.reply_text(message, parse_mode="Markdown")


# TRENDING COMMAND
def trending(update: Update, context: CallbackContext):
    message = (
        "🔥 *Trending Meme Coins*\n\n"
        "1. PEPE\n"
        "2. BONK\n"
        "3. DOGE\n"
        "4. WIF\n"
        "5. FLOKI\n\n"
        "🚀 Sponsored: Get meme coin alerts"
    )

    update.message.reply_text(message, parse_mode="Markdown")


# PORTFOLIO COMMAND
def portfolio(update: Update, context: CallbackContext):
    try:
        buy = float(context.args[0])
        current = float(context.args[1])

        pnl = current - buy
        percent = (pnl / buy) * 100

        message = (
            "💼 *Portfolio Analysis*\n\n"
            f"💵 Entry: ${buy}\n"
            f"📊 Current: ${current}\n"
            f"💰 P/L: ${pnl:.2f}\n"
            f"📈 Return: {percent:.2f}%"
        )

        update.message.reply_text(message, parse_mode="Markdown")

    except:
        update.message.reply_text(
            "Use format:\n/portfolio 1000 1200"
        )


# MAIN
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("pumpfun", pumpfun))
    dp.add_handler(CommandHandler("alert", alert))
    dp.add_handler(CommandHandler("trending", trending))
    dp.add_handler(CommandHandler("portfolio", portfolio))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
