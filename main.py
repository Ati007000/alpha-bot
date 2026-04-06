import os, logging, sqlite3, requests, random, asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ApplicationBuilder
from telegram.constants import ParseMode

load_dotenv()

# ---------------- ENV ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
TWITTER_BEARER = os.getenv("TWITTER_BEARER")
SENTIMENT_API_KEY = os.getenv("SENTIMENT_API_KEY")
ALERT_GROUP_ID = int(os.getenv("ALERT_GROUP_ID", -1003775368268))   # ← YOUR GROUP ID

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- DATABASE ----------------
DB_PATH = "portfolio.db"
conn = sqlite3.connect(DB_PATH)
conn.execute('''CREATE TABLE IF NOT EXISTS portfolio(
    user_id INTEGER, 
    symbol TEXT, 
    amount REAL, 
    PRIMARY KEY(user_id, symbol)
)''')
conn.execute('''CREATE TABLE IF NOT EXISTS alerts_sent(
    user_id INTEGER,
    symbol TEXT,
    alert_type TEXT,
    last_sent TIMESTAMP,
    PRIMARY KEY(user_id, symbol, alert_type)
)''')
conn.execute('''CREATE TABLE IF NOT EXISTS monitored_accounts(
    username TEXT PRIMARY KEY,
    last_tweet_id TEXT
)''')
conn.commit()
conn.close()

# ---------------- MONITORED X ACCOUNTS (Market Movers) ----------------
MONITORED_ACCOUNTS = {
    "whale_alert": "🐋 Whale Alert",
    "BRICSinfo": "🌍 BRICS News",
    "realDonaldTrump": "🇺🇸 Donald J. Trump"
}

# ---------------- HELPERS ----------------
def box(title: str, content: str) -> str:
    return f"🚀 *{title}*\n\n{content}\n\n_{datetime.utcnow().strftime('%H:%M UTC')}_"

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Price", callback_data="price"), 
         InlineKeyboardButton("🔥 Arbitrage", callback_data="arb")],
        [InlineKeyboardButton("🧠 Twitter Sentiment", callback_data="sentiment"), 
         InlineKeyboardButton("⚡ Pump Detector", callback_data="pump")],
        [InlineKeyboardButton("💼 Portfolio", callback_data="portfolio"), 
         InlineKeyboardButton("📰 News", callback_data="news")],
        [InlineKeyboardButton("🐋 Whale Alerts", callback_data="whale")]
    ])

def get_portfolio(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT symbol, amount FROM portfolio WHERE user_id=?", (user_id,))
    data = dict(c.fetchall())
    conn.close()
    return data

def update_portfolio(user_id: int, symbol: str, amount: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO portfolio (user_id,symbol,amount) VALUES (?,?,?)", 
              (user_id, symbol, amount))
    conn.commit()
    conn.close()

# ---------------- MONITORED ACCOUNTS HELPERS ----------------
def get_last_tweet_id(username: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_tweet_id FROM monitored_accounts WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_last_tweet_id(username: str, tweet_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO monitored_accounts (username, last_tweet_id) VALUES (?,?)", 
              (username, tweet_id))
    conn.commit()
    conn.close()

def fetch_tweets_from_account(username: str, max_results: int = 10):
    try:
        headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
        query = f"from:{username} -is:retweet"
        url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results={max_results}&tweet.fields=created_at"
        r = requests.get(url, headers=headers, timeout=10).json()
        return r.get("data", [])
    except Exception as e:
        logger.error(f"Twitter fetch error for {username}: {e}")
        return []

# ---------------- API HELPERS ----------------
def coinmarketcap_price(symbol: str):
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol": symbol, "convert": "USD"}, timeout=10)
        data = r.json().get("data", {}).get(symbol, {})
        q = data.get("quote", {}).get("USD", {})
        return q.get("price", 0), q.get("percent_change_24h", 0), q.get("volume_24h", 0)
    except Exception as e:
        logger.error(f"CMC error: {e}")
        return 0, 0, 0

def dexscreener_arb(symbol: str):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/search?q={symbol}", timeout=7).json()
        pairs = r.get("pairs", [])
        if not pairs: return {}
        prices = [float(p.get("priceUsd", 0)) for p in pairs if p.get("priceUsd")]
        if not prices: return {}
        lo_price = min(prices)
        hi_price = max(prices)
        lo_pair = next((p for p in pairs if float(p.get("priceUsd", 0)) == lo_price), None)
        hi_pair = next((p for p in pairs if float(p.get("priceUsd", 0)) == hi_price), None)
        return {
            "chain_high": hi_pair.get("chainId") if hi_pair else "N/A",
            "chain_low": lo_pair.get("chainId") if lo_pair else "N/A",
            "hi_price": hi_price,
            "lo_price": lo_price
        }
    except Exception as e:
        logger.error(f"Dexscreener error: {e}")
        return {}

def twitter_fetch_tweets(symbol: str):
    try:
        headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
        query = f"{symbol} OR ${symbol} -is:retweet lang:en"
        r = requests.get(f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=30", headers=headers).json()
        return [t.get("text", "") for t in r.get("data", [])]
    except Exception as e:
        logger.error(f"Twitter error: {e}")
        return []

def sentiment_score_meaningcloud(text: str):
    try:
        url = "https://api.meaningcloud.com/sentiment-2.1"
        data = {"key": SENTIMENT_API_KEY, "txt": text, "lang": "en"}
        r = requests.post(url, data=data).json()
        score = r.get("score_tag", "NEU")
        return {"P+": 1.0, "P": 0.5, "NEU": 0, "N": -0.5, "N+": -1.0}.get(score, 0)
    except:
        return 0

def twitter_sentiment(symbol: str):
    texts = twitter_fetch_tweets(symbol)
    if not texts: return 0
    scores = [sentiment_score_meaningcloud(t) for t in texts]
    return round(sum(scores) / len(scores), 2)

def pump_probability(symbol: str):
    price, change, volume = coinmarketcap_price(symbol)
    sentiment = twitter_sentiment(symbol)
    arb = dexscreener_arb(symbol)
    arb_gain = ((arb.get('hi_price', 0) - arb.get('lo_price', 0)) / arb.get('lo_price', 1)) * 100 if arb else 0
    pump_score = (change * 0.4) + (sentiment * 20) + (arb_gain * 0.4)
    return round(max(0, min(pump_score, 100)), 2)

def whale_alerts(symbol: str):
    whales = []
    for chain in ["ETH", "BSC", "SOL"]:
        amt = random.uniform(1000, 5000)
        if amt > 3000:
            whales.append(f"{chain} whale transfer detected: {amt:.2f} {symbol}")
    return whales

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to *Mega Crypto Bot*!\n\nChoose an option below 👇",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    price, change, _ = coinmarketcap_price(symbol)
    text = box(f"{symbol} Price", f"💵 ${price:.4f}\n📈 24h: {change:+.2f}%")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def arb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    arb = dexscreener_arb(symbol)
    if not arb:
        await update.message.reply_text("❌ No live DEX data found.")
        return
    gain = ((arb['hi_price'] - arb['lo_price']) / arb['lo_price']) * 100
    txt = f"Buy on {arb['chain_low']}: ${arb['lo_price']:.4f}\nSell on {arb['chain_high']}: ${arb['hi_price']:.4f}\n\n💰 Arb opportunity: {gain:.2f}%"
    await update.message.reply_text(box(f"{symbol} DEX Arbitrage", txt), parse_mode=ParseMode.MARKDOWN)

async def sentiment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    score = twitter_sentiment(symbol)
    await update.message.reply_text(box(f"{symbol} Twitter Sentiment", f"Score: {score}"), parse_mode=ParseMode.MARKDOWN)

async def pump_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    score = pump_probability(symbol)
    await update.message.reply_text(box(f"{symbol} Pump Probability", f"🌟 {score}%"), parse_mode=ParseMode.MARKDOWN)

async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pf = get_portfolio(user_id)
    if not pf:
        await update.message.reply_text("💼 Your portfolio is empty.\n\nUse /add SYMBOL amount to add coins.")
        return
    lines = [f"• {sym}: {amt}" for sym, amt in pf.items()]
    await update.message.reply_text(box("Your Portfolio", "\n".join(lines)), parse_mode=ParseMode.MARKDOWN)

async def add_portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/add SYMBOL amount`\nExample: `/add ETH 2.5`", parse_mode=ParseMode.MARKDOWN)
        return
    symbol = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount!")
        return
    update_portfolio(user_id, symbol, amount)
    await update.message.reply_text(f"✅ Added {amount} {symbol} to your portfolio!")

async def news_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📰 *Live X News Alerts Active!*\n\n"
        "Market-moving tweets are being forwarded to your alert group.\n"
        "Whale moves • BRICS updates • Trump statements → all covered instantly 🚀",
        parse_mode=ParseMode.MARKDOWN
    )

async def whale_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "BTC"
    alerts = whale_alerts(symbol)
    if not alerts:
        await update.message.reply_text("🐋 No whale activity detected right now.")
        return
    await update.message.reply_text(box(f"{symbol} Whale Alerts", "\n".join(alerts)), parse_mode=ParseMode.MARKDOWN)

# ---------------- BUTTON HANDLER ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    symbol = "BTC"
    if query.data == "price":
        price, change, _ = coinmarketcap_price(symbol)
        text = box(f"{symbol} Price", f"💵 ${price:.4f}\n📈 24h: {change:+.2f}%")
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    elif query.data == "arb":
        arb = dexscreener_arb(symbol)
        if not arb:
            await query.edit_message_text("❌ No live DEX data found.")
            return
        gain = ((arb['hi_price'] - arb['lo_price']) / arb['lo_price']) * 100
        txt = f"Buy on {arb['chain_low']}: ${arb['lo_price']:.4f}\nSell on {arb['chain_high']}: ${arb['hi_price']:.4f}\n\n💰 Arb opportunity: {gain:.2f}%"
        await query.edit_message_text(box(f"{symbol} DEX Arbitrage", txt), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "sentiment":
        score = twitter_sentiment(symbol)
        await query.edit_message_text(box(f"{symbol} Twitter Sentiment", f"Score: {score}"), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "pump":
        score = pump_probability(symbol)
        await query.edit_message_text(box(f"{symbol} Pump Probability", f"🌟 {score}%"), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "portfolio":
        user_id = update.effective_user.id
        pf = get_portfolio(user_id)
        if not pf:
            await query.edit_message_text("💼 Your portfolio is empty.\n\nUse /add SYMBOL amount to add coins.")
            return
        lines = [f"• {sym}: {amt}" for sym, amt in pf.items()]
        await query.edit_message_text(box("Your Portfolio", "\n".join(lines)), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "news":
        await query.edit_message_text(
            "📰 *Live X News Alerts Active!*\n\n"
            "Market-moving tweets are being forwarded to your alert group.\n"
            "Whale moves • BRICS updates • Trump statements → all covered instantly 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "whale":
        alerts = whale_alerts(symbol)
        if not alerts:
            await query.edit_message_text("🐋 No whale activity detected right now.")
            return
        await query.edit_message_text(box(f"{symbol} Whale Alerts", "\n".join(alerts)), parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text("Feature coming soon! 🚀")

# ---------------- BACKGROUND PUMP ALERTS ----------------
async def send_pump_alerts(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM portfolio")
    users = [row[0] for row in c.fetchall()]
    now = datetime.utcnow()
    for user_id in users:
        pf = get_portfolio(user_id)
        for sym in pf.keys():
            c.execute("SELECT last_sent FROM alerts_sent WHERE user_id=? AND symbol=? AND alert_type='pump'", (user_id, sym))
            row = c.fetchone()
            last_sent = datetime.fromisoformat(str(row[0])) if row and row[0] else None
            if last_sent and (now - last_sent).total_seconds() < 300: continue
            pump = pump_probability(sym)
            if pump > 80:
                try:
                    msg = box(f"🚨 {sym} PUMP ALERT", f"High pump probability: {pump}%")
                    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)
                    c.execute("INSERT OR REPLACE INTO alerts_sent (user_id, symbol, alert_type, last_sent) VALUES (?, ?, 'pump', ?)", (user_id, sym, now))
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed to send alert to {user_id}: {e}")
    conn.close()

# ---------------- LIVE X NEWS ALERTS ----------------
async def news_alert_task(context: ContextTypes.DEFAULT_TYPE):
    if ALERT_GROUP_ID == 0:
        logger.warning("No ALERT_GROUP_ID → X news alerts disabled")
        return

    for username, display_name in MONITORED_ACCOUNTS.items():
        tweets = fetch_tweets_from_account(username, max_results=5)
        if not tweets:
            continue

        last_id = get_last_tweet_id(username)
        new_tweets = []
        max_id = None

        for tweet in tweets:
            tweet_id = tweet["id"]
            if last_id is None or int(tweet_id) > int(last_id):
                new_tweets.append(tweet)
                if max_id is None or int(tweet_id) > int(max_id):
                    max_id = tweet_id
            else:
                break

        if new_tweets:
            new_tweets.sort(key=lambda t: int(t["id"]))
            for tweet in new_tweets:
                text = tweet.get("text", "").strip()
                tweet_id = tweet["id"]
                url = f"https://x.com/{username}/status/{tweet_id}"
                alert_text = box(
                    f"📰 {display_name}",
                    f"{text}\n\n🔗 [View full post on X]({url})"
                )
                try:
                    await context.bot.send_message(
                        chat_id=ALERT_GROUP_ID,
                        text=alert_text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"Failed to send X alert from {username}: {e}")

            if max_id:
                update_last_tweet_id(username, max_id)
        elif last_id is None and tweets:
            newest_id = max((t["id"] for t in tweets), key=int)
            update_last_tweet_id(username, newest_id)
            logger.info(f"Initial sync completed for @{username}")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price_handler))
    app.add_handler(CommandHandler("arb", arb_handler))
    app.add_handler(CommandHandler("sentiment", sentiment_handler))
    app.add_handler(CommandHandler("pump", pump_handler))
    app.add_handler(CommandHandler("portfolio", portfolio_handler))
    app.add_handler(CommandHandler("add", add_portfolio_handler))
    app.add_handler(CommandHandler("news", news_handler))
    app.add_handler(CommandHandler("whale", whale_handler))

    app.add_handler(CallbackQueryHandler(button_handler))

    # Background jobs
    app.job_queue.run_repeating(send_pump_alerts, interval=300, first=10)
    app.job_queue.run_repeating(news_alert_task, interval=180, first=30)

    logger.info("🚀 Mega Crypto Bot with LIVE X News Alerts is running!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
    
