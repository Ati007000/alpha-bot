import os
import logging
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# -------------------- ENV --------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN missing!")
if not CMC_API_KEY:
    raise ValueError("COINMARKETCAP_API_KEY missing!")

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- DATABASE --------------------
DB_PATH = "portfolio.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                    user_id INTEGER,
                    symbol TEXT,
                    amount REAL,
                    PRIMARY KEY (user_id, symbol)
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
                    user_id INTEGER,
                    symbol TEXT,
                    target REAL,
                    above INTEGER,
                    PRIMARY KEY (user_id, symbol, target)
                 )''')
    conn.commit()
    conn.close()

init_db()

def get_portfolio(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT symbol, amount FROM portfolio WHERE user_id=?", (user_id,))
    data = dict(c.fetchall())
    conn.close()
    return data

def update_portfolio(user_id, symbol, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO portfolio (user_id, symbol, amount) VALUES (?, ?, ?)",
        (user_id, symbol, amount)
    )
    conn.commit()
    conn.close()

# -------------------- HELPERS --------------------
def box(title: str, content: str) -> str:
    return f"🚀 *{title}*\n\n{content}\n\n_Alpha Bot Premium • {datetime.utcnow().strftime('%H:%M UTC')}_"

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Price", callback_data="price"), InlineKeyboardButton("🔥 Market Movers", callback_data="movers")],
        [InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"), InlineKeyboardButton("📰 News + Suggestion", callback_data="news")],
        [InlineKeyboardButton("🔔 Price Alerts", callback_data="alerts"), InlineKeyboardButton("👁 Watchlist", callback_data="watchlist")]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------------------- API HELPERS --------------------
def get_price(symbol: str):
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=10)
        data = r.json()
        coin = data["data"].get(symbol)
        if isinstance(coin, list):
            coin = coin[0]
        q = coin["quote"]["USD"]
        price = q["price"]
        change24h = q.get("percent_change_24h", 0)
        return price, change24h
    except Exception as e:
        logger.warning(f"Error fetching price for {symbol}: {e}")
        return 0, 0

def get_latest_news(limit=5):
    try:
        r = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=EN", timeout=10)
        return r.json().get("Data", [])[:limit]
    except:
        return []

def analyze_news(symbol: str, change24h: float, news_items: list):
    lower_news = " ".join([item["title"].lower() + " " + item.get("body", "").lower() for item in news_items])
    suggestion = "NEUTRAL"
    reason = "No strong signals detected"

    if any(kw in lower_news for kw in ["war", "iran", "middle east", "geopolitical", "conflict", "strait of hormuz", "oil supply"]):
        suggestion = "SELL"
        reason = "Geopolitical tensions detected → risk-off sentiment"
    elif any(kw in lower_news for kw in ["cpi higher", "inflation hot", "fed hike", "hawkish"]):
        suggestion = "SELL"
        reason = "Macro: higher CPI / hawkish Fed → bearish"
    elif any(kw in lower_news for kw in ["cpi lower", "inflation cooled", "fed cut", "dovish"]):
        suggestion = "BUY"
        reason = "Macro: CPI cooled / dovish Fed → bullish"
    elif change24h > 5:
        suggestion = "BUY"
        reason = "Strong bullish momentum"
    elif change24h < -5:
        suggestion = "SELL"
        reason = "Bearish momentum"
    return suggestion, reason

# -------------------- COMMAND HANDLERS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Alpha Bot Premium! Use the menu below:",
        reply_markup=main_menu_keyboard()
    )

async def news_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "BTC")
    price, change24h = get_price(symbol)
    news_items = get_latest_news()
    news_summary = "\n".join([f"• {item['title'][:90]}..." for item in news_items])
    suggestion, reason = analyze_news(symbol, change24h, news_items)
    msg = box(
        f"{symbol} MARKET INTELLIGENCE",
        f"💵 Price: `${price:,.6f}`\n📈 24h: `{change24h:+.2f}%`\n\n"
        f"📰 Recent Headlines:\n{news_summary[:700]}...\n\n"
        f"🔮 Recommendation: {suggestion}\nReason: {reason}\n\n"
        f"⚠️ AI-assisted analysis — not financial advice. DYOR!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

# Example placeholders for other commands
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "BTC")
    price, change24h = get_price(symbol)
    msg = box(f"{symbol} Price", f"💵 ${price:,.6f}\n📈 24h Change: {change24h:+.2f}%")
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buy command placeholder — implement your logic.")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sell command placeholder — implement your logic.")

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pf = get_portfolio(user_id)
    if not pf:
        await update.message.reply_text("Your portfolio is empty.")
        return
    lines = [f"{sym}: {amt}" for sym, amt in pf.items()]
    await update.message.reply_text(box("Your Portfolio", "\n".join(lines)), parse_mode=ParseMode.MARKDOWN_V2)

# -------------------- MAIN --------------------
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_suggest))
    app.add_handler(CommandHandler("suggest", news_suggest))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("portfolio", portfolio))

    logger.info("🚀 Alpha Bot Premium ready!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
