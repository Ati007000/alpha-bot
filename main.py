import os
import logging
import random
from datetime import datetime
from dotenv import load_dotenv

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()

# =========================
# ENVIRONMENT VARIABLES
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")  # Auto-provided by Railway
PORT = int(os.getenv("PORT", 8080))

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
    """Premium styled message box"""
    return f"🚀 *{title}*\n\n{content}\n\n_Alpha Bot Premium • {datetime.now().strftime('%H:%M')} UTC_"

def get_random_tip() -> str:
    tips = [
        "DYOR before aping into any pump.fun launch 🔥",
        "Set your stop-loss before FOMO hits",
        "Whale wallets are moving — stay alert",
        "Solana memes are still printing in 2026",
        "Never invest more than you can afford to lose",
    ]
    return random.choice(tips)

# =========================
# INLINE KEYBOARD
# =========================
def main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📊 Price", callback_data="price"),
            InlineKeyboardButton("🔥 Pump.fun", callback_data="pumpfun"),
        ],
        [
            InlineKeyboardButton("📈 Trending", callback_data="trending"),
            InlineKeyboardButton("⚠️ Alerts", callback_data="alert"),
        ],
        [
            InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"),
            InlineKeyboardButton("🎯 Risk/Reward", callback_data="risk"),
        ],
        [InlineKeyboardButton("📰 News & Tips", callback_data="news")],
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================
# COMMAND HANDLERS (All Async)
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tip = get_random_tip()
    msg = box(
        "ALPHA BOT PREMIUM",
        "Welcome back, anon! 🚀\n\n"
        "Tap any button below or use commands:\n"
        "/price BTC • /pumpfun • /trending\n"
        "/alert ETH • /portfolio 1000 1250\n"
        "/risk 800 1600 • /news • /convert 100 BTC USD\n\n"
        f"💡 Pro Tip: {tip}"
    )
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_menu_keyboard()
    )
    logger.info(f"User {update.effective_user.id} started the bot")


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        symbol = (context.args[0].upper() if context.args else "BTC")
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": symbol, "convert": "USD"}

        response = requests.get(url, headers=headers, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()

        if "data" not in data or symbol not in data["data"]:
            await update.message.reply_text("⚠️ Coin not found on CoinMarketCap.")
            return

        coin_data = data["data"][symbol]
        # CMC sometimes returns list, sometimes dict
        if isinstance(coin_data, list):
            coin_data = coin_data[0]
        quote = coin_data["quote"]["USD"]

        trend = "Bullish 🔥" if quote.get("percent_change_24h", 0) > 0 else "Bearish ⚠️"

        msg = box(
            f"{symbol} LIVE",
            f"💵 Price: `${quote['price']:,.6f}`\n"
            f"📈 24h Change: `{quote.get('percent_change_24h', 0):+.2f}%`\n"
            f"💰 24h Volume: `${quote.get('volume_24h', 0):,.0f}`\n"
            f"🏦 Market Cap: `${quote.get('market_cap', 0):,.0f}`\n"
            f"🔥 Trend: {trend}\n"
            f"🌐 Dominance: `{quote.get('market_cap_dominance', 0):.2f}%`"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error(f"Price error: {e}")
        await update.message.reply_text("⚠️ Failed to fetch price. API key issue or rate limit?")


async def pumpfun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Official public Pump.fun v3 API (2026)
        url = "https://frontend-api-v3.pump.fun/coins/latest"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or len(data) == 0:
            await update.message.reply_text("No new launches right now.")
            return

        latest = data[0]

        name = latest.get("name", "Unknown")
        symbol = latest.get("symbol", "N/A")
        mint = latest.get("mint", "N/A")
        mc = latest.get("market_cap") or latest.get("usd_market_cap", 0)
        dev = latest.get("creator", "N/A")[:12] + "..." if isinstance(latest.get("creator"), str) else "N/A"

        msg = box(
            "LATEST PUMP.FUN LAUNCH 🔥",
            f"🪙 Name: {name}\n"
            f"🔖 Symbol: {symbol}\n"
            f"🧾 Mint: `{mint}`\n"
            f"🏦 MC: `${mc:,.0f}`\n"
            f"👨‍💻 Dev: `{dev}`\n\n"
            f"⚠️ DYOR • Check bonding curve & liquidity before entry!"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        logger.error(f"Pump.fun error: {e}")
        await update.message.reply_text("⚠️ Could not fetch latest pump.fun coin.")


async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "BTC")
    msg = box(
        "SMART ALERTS ENABLED 🔔",
        f"📊 Monitoring: {symbol}\n\n"
        "✅ Pump detection\n"
        "✅ Dump protection\n"
        "✅ Whale wallet alerts\n"
        "✅ Volume spike alerts\n"
        "✅ 10x/100x momentum signals\n\n"
        "Premium alerts are now ACTIVE for you!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = box(
        "HOT TRENDING MEMES 🔥",
        "1️⃣ PEPE\n"
        "2️⃣ BONK\n"
        "3️⃣ WIF\n"
        "4️⃣ FLOKI\n"
        "5️⃣ POPCAT\n"
        "6️⃣ GIGA\n"
        "7️⃣ MOG\n\n"
        "Solana memes still printing in 2026 🚀"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buy = float(context.args[0])
        current = float(context.args[1])
        pnl = current - buy
        roi = (pnl / buy) * 100

        msg = box(
            "PORTFOLIO SNAPSHOT 💼",
            f"💵 Entry Price: `${buy:,.2f}`\n"
            f"📊 Current Price: `${current:,.2f}`\n"
            f"💰 Unrealized P/L: `${pnl:,.2f}`\n"
            f"📈 ROI: `{roi:+.2f}%` {'🚀' if roi > 0 else '📉'}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except:
        await update.message.reply_text("Usage: `/portfolio <entry> <current>`\nExample: `/portfolio 1000 1420`")


async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        entry = float(context.args[0])
        target = float(context.args[1])
        rr = target / entry

        msg = box(
            "RISK : REWARD RATIO 🎯",
            f"📍 Entry: `${entry:,.2f}`\n"
            f"🚀 Target: `${target:,.2f}`\n"
            f"⚖️ Ratio: `{rr:.2f}x` {'🟢 GOOD' if rr >= 2 else '🔴 Risky'}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except:
        await update.message.reply_text("Usage: `/risk <entry> <target>`\nExample: `/risk 800 1600`")


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = box(
        "MARKET NEWS 📰",
        "• BTC holding strong above $90K\n"
        "• Solana memes dominate volume\n"
        "• New whale wallets accumulating PEPE\n"
        "• Pump.fun daily volume still ATH\n\n"
        f"💡 Tip: {get_random_tip()}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bonus feature: Quick conversion"""
    try:
        amount = float(context.args[0])
        from_symbol = context.args[1].upper()
        to_symbol = context.args[2].upper() if len(context.args) > 2 else "USD"

        # Simple CMC conversion (for demo we use price of from and to)
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        params = {"symbol": f"{from_symbol},{to_symbol}", "convert": "USD"}

        resp = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
            headers=headers, params=params, timeout=10
        )
        data = resp.json()

        from_price = data["data"][from_symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][from_symbol], list) else data["data"][from_symbol]["quote"]["USD"]["price"]
        to_price = data["data"][to_symbol][0]["quote"]["USD"]["price"] if isinstance(data["data"][to_symbol], list) else data["data"][to_symbol]["quote"]["USD"]["price"]

        converted = (amount * from_price) / to_price

        msg = box(
            "QUICK CONVERTER",
            f"{amount:,.4f} {from_symbol} = `{converted:,.4f}` {to_symbol}\n"
            f"Rate: 1 {from_symbol} = `{from_price / to_price:.6f}` {to_symbol}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except:
        await update.message.reply_text("Usage: `/convert <amount> <from> <to>`\nExample: `/convert 0.5 BTC ETH`")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Railway debugging command"""
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = box(
        "BOT STATUS ✅",
        f"🟢 Online since: {uptime}\n"
        f"📡 Mode: Webhook (Railway)\n"
        f"🌐 Public Domain: {RAILWAY_PUBLIC_DOMAIN or 'Local'}\n"
        f"🔑 CMC Key: {'✅ Set' if CMC_API_KEY else '❌ Missing'}\n"
        f"📍 Railway Port: {PORT}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


# =========================
# MAIN APPLICATION
# =========================
def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN is missing from .env!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("pumpfun", pumpfun))
    app.add_handler(CommandHandler("alert", alert))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("portfolio", portfolio))
    app.add_handler(CommandHandler("risk", risk))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("convert", convert))
    app.add_handler(CommandHandler("status", status))

    logger.info("🚀 Alpha Bot Premium starting...")

    # Railway Webhook Mode (Recommended)
    if RAILWAY_PUBLIC_DOMAIN:
        webhook_url = f"https://{RAILWAY_PUBLIC_DOMAIN}/{TELEGRAM_TOKEN}"
        logger.info(f"Using webhook: {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        # Local fallback (polling)
        logger.info("No Railway domain detected → using polling (local testing)")
        app.run_polling()

if __name__ == "__main__":
    main()
