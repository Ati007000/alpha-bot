import os
import logging
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
    data = dict(c.fetchall())
    conn.close()
    return data

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
        [InlineKeyboardButton("📊 Price", callback_data="price"), InlineKeyboardButton("🔥 Pump.fun", callback_data="pumpfun")],
        [InlineKeyboardButton("💰 Buy", callback_data="buy"), InlineKeyboardButton("💸 Sell", callback_data="sell")],
        [InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"), InlineKeyboardButton("📰 News + Suggestion", callback_data="news")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ====================== ENHANCED NEWS + SMART SUGGESTION ======================
def get_latest_news():
    try:
        r = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=EN", timeout=10)
        return r.json().get("Data", [])[:8]
    except:
        return []

async def news_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "BTC")
    
    # Live price
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=12)
        data = r.json()
        coin = data["data"].get(symbol)
        if isinstance(coin, list): coin = coin[0]
        q = coin["quote"]["USD"]
        price = q["price"]
        change24h = q.get("percent_change_24h", 0)
    except:
        price = 0
        change24h = 0

    # Get news
    news_items = get_latest_news()
    news_summary = "\n".join([f"• {item['title'][:90]}..." for item in news_items])

    # Enhanced suggestion logic (includes war/geopolitics)
    lower_news = " ".join([item["title"].lower() + " " + item.get("body", "").lower() for item in news_items])
    
    suggestion = "NEUTRAL"
    reason = "No strong signals detected"

    if any(kw in lower_news for kw in ["war", "iran", "middle east", "geopolitical", "conflict", "strait of hormuz", "oil supply"]):
        suggestion = "SELL"
        reason = "War/geopolitical tensions (e.g. Iran conflict) driving oil prices up → inflation risk & risk-off sentiment"
    elif any(kw in lower_news for kw in ["cpi higher", "inflation hot", "fed hike", "hawkish", "rate hike"]):
        suggestion = "SELL"
        reason = "Higher-than-expected CPI or hawkish Fed signals → higher rates pressure on crypto"
    elif any(kw in lower_news for kw in ["cpi lower", "inflation cooled", "fed cut", "rate cut", "dovish"]):
        suggestion = "BUY"
        reason = "Positive macro (lower CPI / Fed easing) → bullish for risk assets like crypto"
    elif change24h > 5:
        suggestion = "BUY"
        reason = "Strong bullish momentum"
    elif change24h < -5:
        suggestion = "SELL"
        reason = "Bearish momentum"

    msg = box(
        f"{symbol} MARKET INTELLIGENCE",
        f"💵 Price: `${price:,.6f}`\n"
        f"📈 24h: `{change24h:+.2f}%`\n\n"
        f"📰 Recent Headlines Impact:\n{news_summary[:700]}...\n\n"
        f"🔮 **Recommendation: {suggestion}**\n"
        f"Reason: {reason}\n\n"
        f"⚠️ This is AI-assisted analysis based on public news — not financial advice. Always DYOR!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

# ====================== OTHER COMMANDS (Buy, Sell, Portfolio, Price) ======================
# Keep your existing buy, sell, portfolio, price functions here (from the previous version)
# For brevity I'm not repeating them — just paste them in the same file.

# Example placeholders (replace with your working versions):
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buy command works (implement your previous logic here)")

# ... similarly for sell, portfolio, price, start, ping

# ====================== MAIN ======================
def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN missing!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_suggest))
    app.add_handler(CommandHandler("suggest", news_suggest))
    # Add your other handlers: buy, sell, portfolio, price, ping

    logger.info("🚀 Alpha Bot Premium v4 (with War + Macro Suggestions) starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
