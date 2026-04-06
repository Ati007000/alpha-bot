import os
import logging
import random
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory portfolio (user_id -> coin -> amount)
portfolio = defaultdict(lambda: defaultdict(float))

def box(title: str, content: str) -> str:
    return f"🚀 *{title}*\n\n{content}\n\n_Alpha Bot • {datetime.now().strftime('%H:%M')} UTC_"

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = box(
        "ALPHA BOT PREMIUM",
        "Bot is online and responding! 🚀\n\n"
        "Available commands:\n"
        "/price BTC\n"
        "/pumpfun\n"
        "/buy 1000 BTC\n"
        "/sell 500 BTC\n"
        "/portfolio\n"
        "/ping"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive and responding via polling!")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        symbol = (context.args[0].upper() if context.args else "BTC")
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": symbol, "convert": "USD"}

        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        coin = data["data"].get(symbol)
        if not coin:
            await update.message.reply_text("⚠️ Coin not found.")
            return

        if isinstance(coin, list):
            coin = coin[0]
        q = coin["quote"]["USD"]

        trend = "Bullish 🔥" if q.get("percent_change_24h", 0) > 0 else "Bearish ⚠️"

        msg = box(
            f"{symbol} LIVE",
            f"💵 Price: `${q['price']:,.6f}`\n"
            f"📈 24h: `{q.get('percent_change_24h', 0):+.2f}%`\n"
            f"💰 Vol: `${q.get('volume_24h', 0):,.0f}`\n"
            f"🏦 MC: `${q.get('market_cap', 0):,.0f}`\n"
            f"🔥 Trend: {trend}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Price error: {e}")
        await update.message.reply_text("⚠️ Failed to fetch price. Try again later.")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        symbol = context.args[1].upper()

        # Get current price
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": symbol, "convert": "USD"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        price = data["data"][symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][symbol], list) else data["data"][symbol]["quote"]["USD"]["price"]

        cost = amount * price
        user_id = update.effective_user.id
        portfolio[user_id][symbol] += amount

        msg = box(
            "BUY ORDER EXECUTED ✅",
            f"🪙 Bought: `{amount}` {symbol}\n"
            f"💵 Price: `${price:,.6f}`\n"
            f"💰 Total Cost: `${cost:,.2f}`\n"
            f"📍 New holding: `{portfolio[user_id][symbol]:.4f}` {symbol}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        await update.message.reply_text("Usage: `/buy <amount> <symbol>`\nExample: `/buy 1000 BTC`")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        symbol = context.args[1].upper()

        user_id = update.effective_user.id
        if portfolio[user_id][symbol] < amount:
            await update.message.reply_text(f"❌ You don't have enough {symbol} to sell.")
            return

        # Get current price
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": symbol, "convert": "USD"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        price = data["data"][symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][symbol], list) else data["data"][symbol]["quote"]["USD"]["price"]

        revenue = amount * price
        portfolio[user_id][symbol] -= amount

        msg = box(
            "SELL ORDER EXECUTED ✅",
            f"🪙 Sold: `{amount}` {symbol}\n"
            f"💵 Price: `${price:,.6f}`\n"
            f"💰 Revenue: `${revenue:,.2f}`\n"
            f"📍 Remaining: `{portfolio[user_id][symbol]:.4f}` {symbol}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        await update.message.reply_text("Usage: `/sell <amount> <symbol>`\nExample: `/sell 500 BTC`")

async def show_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not portfolio[user_id]:
        await update.message.reply_text("Your portfolio is empty. Use /buy to start trading!")
        return

    lines = []
    total_value = 0
    for symbol, amount in portfolio[user_id].items():
        try:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
            params = {"symbol": symbol, "convert": "USD"}
            r = requests.get(url, headers=headers, params=params, timeout=8)
            data = r.json()
            price = data["data"][symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][symbol], list) else data["data"][symbol]["quote"]["USD"]["price"]
            value = amount * price
            total_value += value
            lines.append(f"• `{amount:.4f}` {symbol} @ `${price:,.6f}` = `${value:,.2f}`")
        except:
            lines.append(f"• `{amount:.4f}` {symbol} (price unavailable)")

    msg = box(
        "YOUR PORTFOLIO 💼",
        "\n".join(lines) + f"\n\n💰 **Total Value:** `${total_value:,.2f}` USD"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

# ====================== MAIN ======================
def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN missing!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("portfolio", show_portfolio))

    logger.info("🚀 Alpha Bot starting with POLLING mode...")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
