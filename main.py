import os
import logging
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
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

def remove_from_portfolio(user_id, symbol):
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute("DELETE FROM portfolio WHERE user_id=? AND symbol=?", (user_id, symbol))
    conn.commit()
    conn.close()


# ====================== HELPERS ======================
def escape_md(text: str) -> str:
    """Escape special chars for MarkdownV2."""
    special = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special else c for c in str(text))

def send_text(text: str) -> str:
    """Plain text box — no MarkdownV2, avoids parse errors."""
    return text

def main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📊 Price", callback_data="menu_price"),
            InlineKeyboardButton("📰 News + Suggestion", callback_data="menu_news"),
        ],
        [
            InlineKeyboardButton("💼 Portfolio", callback_data="menu_portfolio"),
            InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ====================== PRICE ======================
def fetch_price(symbol: str):
    """Returns (price, change_24h) or (None, None) on error."""
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers,
                         params={"symbol": symbol, "convert": "USD"}, timeout=12)
        r.raise_for_status()
        data = r.json()
        coin = data["data"].get(symbol)
        if isinstance(coin, list):
            coin = coin[0]
        q = coin["quote"]["USD"]
        return q["price"], q.get("percent_change_24h", 0)
    except Exception as e:
        logger.warning(f"Price fetch failed for {symbol}: {e}")
        return None, None


# ====================== NEWS + SUGGESTION ======================
def get_latest_news():
    try:
        r = requests.get(
            "https://min-api.cryptocompare.com/data/v2/news/?lang=EN", timeout=10
        )
        return r.json().get("Data", [])[:8]
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")
        return []

def build_suggestion(change24h, news_items):
    lower_news = " ".join(
        item["title"].lower() + " " + item.get("body", "").lower()
        for item in news_items
    )

    if any(kw in lower_news for kw in
           ["war", "iran", "middle east", "geopolitical", "conflict",
            "strait of hormuz", "oil supply"]):
        return "SELL", "War/geopolitical tensions driving inflation risk & risk-off sentiment"
    elif any(kw in lower_news for kw in
             ["cpi higher", "inflation hot", "fed hike", "hawkish", "rate hike"]):
        return "SELL", "Hawkish Fed / hot CPI signals → higher rates pressure crypto"
    elif any(kw in lower_news for kw in
             ["cpi lower", "inflation cooled", "fed cut", "rate cut", "dovish"]):
        return "BUY", "Dovish macro (lower CPI / Fed easing) → bullish for risk assets"
    elif change24h is not None and change24h > 5:
        return "BUY", "Strong bullish 24h momentum"
    elif change24h is not None and change24h < -5:
        return "SELL", "Bearish 24h momentum"

    return "NEUTRAL", "No strong signals detected"

async def reply(update: Update, text: str):
    """Reply whether the update came from a message or a callback query."""
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text)


# ====================== COMMAND HANDLERS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Trader"
    msg = (
        f"👋 Welcome, {name}!\n\n"
        "🚀 Alpha Bot Premium — your crypto intelligence assistant.\n\n"
        "Commands:\n"
        "/price BTC — live price\n"
        "/news BTC — news + smart suggestion\n"
        "/buy BTC 0.5 — add to portfolio\n"
        "/sell BTC 0.25 — remove from portfolio\n"
        "/portfolio — view holdings\n"
        "/ping — health check\n"
    )
    await update.message.reply_text(msg, reply_markup=main_menu_keyboard())


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online!")


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    price, change24h = fetch_price(symbol)

    if price is None:
        await reply(update, f"❌ Could not fetch price for {symbol}. Check the symbol or API key.")
        return

    arrow = "📈" if change24h >= 0 else "📉"
    msg = (
        f"📊 {symbol} Price\n"
        f"{'─'*24}\n"
        f"💵 Price : ${price:,.6f}\n"
        f"{arrow} 24h    : {change24h:+.2f}%\n"
        f"{'─'*24}\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M')} UTC"
    )
    await reply(update, msg)


async def news_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"

    price, change24h = fetch_price(symbol)
    news_items = get_latest_news()
    suggestion, reason = build_suggestion(change24h, news_items)

    headlines = "\n".join(
        f"• {item['title'][:85]}..." for item in news_items
    ) or "No headlines available."

    price_line = f"${price:,.6f}" if price else "N/A"
    change_line = f"{change24h:+.2f}%" if change24h is not None else "N/A"

    msg = (
        f"🔍 {symbol} Market Intelligence\n"
        f"{'─'*28}\n"
        f"💵 Price : {price_line}\n"
        f"📈 24h   : {change_line}\n\n"
        f"📰 Recent Headlines:\n{headlines}\n\n"
        f"{'─'*28}\n"
        f"🔮 Recommendation : {suggestion}\n"
        f"💡 Reason         : {reason}\n"
        f"{'─'*28}\n"
        f"⚠️ AI-assisted analysis — not financial advice. DYOR!\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M')} UTC"
    )
    await reply(update, msg)


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await reply(update, "Usage: /buy BTC 0.5")
        return
    symbol = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await reply(update, "❌ Invalid amount. Example: /buy BTC 0.5")
        return

    user_id = update.effective_user.id
    portfolio = get_portfolio(user_id)
    current = portfolio.get(symbol, 0)
    new_total = current + amount
    update_portfolio(user_id, symbol, new_total)

    await reply(update, f"✅ Added {amount} {symbol} to your portfolio.\nNew total: {new_total} {symbol}")


async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await reply(update, "Usage: /sell BTC 0.25")
        return
    symbol = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await reply(update, "❌ Invalid amount. Example: /sell BTC 0.25")
        return

    user_id = update.effective_user.id
    portfolio = get_portfolio(user_id)
    current = portfolio.get(symbol, 0)

    if amount > current:
        await reply(update, f"❌ You only hold {current} {symbol}.")
        return

    new_total = current - amount
    if new_total <= 0:
        remove_from_portfolio(user_id, symbol)
        await reply(update, f"✅ Removed {symbol} from your portfolio.")
    else:
        update_portfolio(user_id, symbol, new_total)
        await reply(update, f"✅ Sold {amount} {symbol}. Remaining: {new_total} {symbol}")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    holdings = get_portfolio(user_id)

    if not holdings:
        await reply(update, "📭 Your portfolio is empty. Use /buy BTC 0.5 to add holdings.")
        return

    total_usd = 0.0
    lines = []
    for symbol, amount in holdings.items():
        price, change24h = fetch_price(symbol)
        if price:
            value = price * amount
            total_usd += value
            arrow = "📈" if (change24h or 0) >= 0 else "📉"
            lines.append(
                f"{arrow} {symbol}: {amount} × ${price:,.4f} = ${value:,.2f}  ({change24h:+.2f}%)"
            )
        else:
            lines.append(f"• {symbol}: {amount} (price unavailable)")

    msg = (
        f"💼 Your Portfolio\n"
        f"{'─'*28}\n"
        + "\n".join(lines) +
        f"\n{'─'*28}\n"
        f"💰 Total Value: ${total_usd:,.2f} USD\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M')} UTC"
    )
    await reply(update, msg)


# ====================== CALLBACK QUERY HANDLER ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Dismiss the loading spinner on the button

    data = query.data

    if data == "menu_price":
        await query.message.reply_text("Send: /price BTC (replace BTC with any symbol)")
    elif data == "menu_news":
        await query.message.reply_text("Send: /news BTC (replace BTC with any symbol)")
    elif data == "menu_portfolio":
        context.args = []
        await portfolio_command(update, context)
    elif data == "menu_help":
        await query.message.reply_text(
            "📖 Commands:\n"
            "/price BTC — live price\n"
            "/news BTC — news + suggestion\n"
            "/buy BTC 0.5 — add to portfolio\n"
            "/sell BTC 0.25 — reduce holdings\n"
            "/portfolio — view all holdings\n"
            "/ping — check bot status"
        )


# ====================== MAIN ======================
def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN missing! Check your .env file.")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("news", news_suggest))
    app.add_handler(CommandHandler("suggest", news_suggest))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("portfolio", portfolio_command))

    # Inline keyboard button handler
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 Alpha Bot Premium starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
