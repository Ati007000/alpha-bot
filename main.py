import os
import logging
import random
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    symbol TEXT,
                    amount REAL,
                    PRIMARY KEY (user_id, symbol)
                 )''')
    conn.commit()
    conn.close()

init_db()

def get_portfolio(user_id):
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute("SELECT symbol, amount FROM portfolio WHERE user_id=?", (user_id,))
    data = c.fetchall()
    conn.close()
    return dict(data)

def update_portfolio(user_id, symbol, amount):
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, ?)",
              (user_id, symbol, amount))
    conn.commit()
    conn.close()

# ====================== HELPERS ======================
def box(title: str, content: str) -> str:
    return f"🚀 *{title}*\n\n{content}\n\n_Alpha Bot Premium • {datetime.now().strftime('%H:%M')} UTC_"

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Price", callback_data="price"),
         InlineKeyboardButton("🔥 Pump.fun", callback_data="pumpfun")],
        [InlineKeyboardButton("💰 Buy", callback_data="buy"),
         InlineKeyboardButton("💸 Sell", callback_data="sell")],
        [InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"),
         InlineKeyboardButton("📋 Watchlist", callback_data="watchlist")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        box("ALPHA BOT PREMIUM", "Welcome back, anon! 🚀\n\nChoose an option below or type any command."),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu_keyboard()
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is fully responsive and running on Railway!")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (same solid price function as before - kept for brevity)
    try:
        symbol = (context.args[0].upper() if context.args else "BTC")
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": symbol, "convert": "USD"}
        r = requests.get(url, headers=headers, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        coin = data["data"].get(symbol)
        if not coin: 
            await update.message.reply_text("⚠️ Coin not found.")
            return
        if isinstance(coin, list): coin = coin[0]
        q = coin["quote"]["USD"]
        trend = "Bullish 🔥" if q.get("percent_change_24h", 0) > 0 else "Bearish ⚠️"
        msg = box(f"{symbol} LIVE", f"💵 `${q['price']:,.6f}`\n📈 `{q.get('percent_change_24h', 0):+.2f}%`\n💰 Vol `${q.get('volume_24h', 0):,.0f}`\n🏦 MC `${q.get('market_cap', 0):,.0f}`\n🔥 {trend}")
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(e)
        await update.message.reply_text("⚠️ Price fetch failed.")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        symbol = context.args[1].upper()
        user_id = update.effective_user.id

        # Get live price
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=10)
        data = r.json()
        price = data["data"][symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][symbol], list) else data["data"][symbol]["quote"]["USD"]["price"]

        cost = amount * price

        # Update portfolio
        current = get_portfolio(user_id).get(symbol, 0)
        update_portfolio(user_id, symbol, current + amount)

        await update.message.reply_text(
            box("BUY EXECUTED ✅", f"🪙 `{amount}` {symbol}\n💵 @ `${price:,.6f}`\n💰 Cost `${cost:,.2f}`\n📍 New balance `{current + amount:.4f}` {symbol}"),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except:
        await update.message.reply_text("Usage: `/buy <amount> <symbol>`\nExample: `/buy 1000 BTC`")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(context.args[0])
        symbol = context.args[1].upper()
        user_id = update.effective_user.id

        current = get_portfolio(user_id).get(symbol, 0)
        if current < amount:
            await update.message.reply_text("❌ Not enough balance!")
            return

        # Get live price
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=10)
        data = r.json()
        price = data["data"][symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][symbol], list) else data["data"][symbol]["quote"]["USD"]["price"]

        revenue = amount * price
        update_portfolio(user_id, symbol, current - amount)

        await update.message.reply_text(
            box("SELL EXECUTED ✅", f"🪙 `{amount}` {symbol}\n💵 @ `${price:,.6f}`\n💰 Revenue `${revenue:,.2f}`\n📍 Remaining `{current - amount:.4f}` {symbol}"),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except:
        await update.message.reply_text("Usage: `/sell <amount> <symbol>`\nExample: `/sell 500 BTC`")

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    holdings = get_portfolio(user_id)
    if not holdings:
        await update.message.reply_text("Portfolio empty. Use /buy to start!")
        return

    lines = []
    total_value = 0
    for symbol, amount in holdings.items():
        try:
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
            r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=8)
            price = r.json()["data"][symbol][0]["quote"]["USD"]["price"]
            value = amount * price
            total_value += value
            lines.append(f"• `{amount:.4f}` {symbol} @ `${price:,.6f}` = `${value:,.2f}`")
        except:
            lines.append(f"• `{amount:.4f}` {symbol} (price N/A)")

    await update.message.reply_text(
        box("YOUR PORTFOLIO 💼", "\n".join(lines) + f"\n\n💰 **Total Value:** `${total_value:,.2f}` USD"),
        parse_mode=ParseMode.MARKDOWN_V2
    )

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
    app.add_handler(CommandHandler("portfolio", portfolio))

    logger.info("🚀 Alpha Bot Premium v2 starting (polling)...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
