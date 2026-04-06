import os, logging, sqlite3, requests, random, asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ApplicationBuilder, JobQueue
from telegram.constants import ParseMode

load_dotenv()

# ---------------- ENV ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
TWITTER_BEARER = os.getenv("TWITTER_BEARER")
SENTIMENT_API_KEY = os.getenv("SENTIMENT_API_KEY")
ALERT_GROUP_ID = int(os.getenv("ALERT_GROUP_ID"))

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

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
conn.commit()
conn.close()

# ---------------- HELPERS ----------------
def box(title, content):
    return f"🚀 *{title}*\n\n{content}\n\n_SuperIntelligent Bot • {datetime.utcnow().strftime('%H:%M UTC')}_"

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Price", "price"), InlineKeyboardButton("🔥 Arbitrage", "arb")],
        [InlineKeyboardButton("🧠 Twitter Sentiment", "sentiment"), InlineKeyboardButton("⚡ Pump Detector", "pump")],
        [InlineKeyboardButton("💼 Portfolio", "portfolio"), InlineKeyboardButton("📰 News", "news")],
        [InlineKeyboardButton("🐋 Whale Alerts", "whale")]
    ])

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
    c.execute("INSERT OR REPLACE INTO portfolio (user_id,symbol,amount) VALUES (?,?,?)", (user_id,symbol,amount))
    conn.commit()
    conn.close()

# ---------------- API HELPERS ----------------
def coinmarketcap_price(symbol):
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
        r = requests.get(url, headers=headers, params={"symbol":symbol,"convert":"USD"},timeout=10)
        data = r.json().get("data", {}).get(symbol, {})
        q = data.get("quote",{}).get("USD",{})
        return q.get("price",0), q.get("percent_change_24h",0), q.get("volume_24h",0)
    except: return 0,0,0

def dexscreener_arb(symbol):
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/search?q={symbol}", timeout=7).json()
        pairs = r.get("pairs",[])
        best = {}
        for p in pairs:
            chain = p.get("chainId")
            price = float(p.get("priceUsd",0))
            best.setdefault(chain, price)
        if not best: return {}
        highest = max(best, key=best.get)
        lowest = min(best, key=best.get)
        return {"chain_high": highest, "chain_low": lowest, "hi_price":best[highest], "lo_price":best[lowest]}
    except: return {}

def twitter_fetch_tweets(symbol):
    headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
    query = f"{symbol} -is:retweet lang:en"
    r = requests.get(f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=30", headers=headers).json()
    return [t.get("text","") for t in r.get("data",[])]

def sentiment_score_meaningcloud(text):
    url = "https://api.meaningcloud.com/sentiment-2.1"
    data = {"key": SENTIMENT_API_KEY, "txt": text, "lang":"en"}
    try:
        r = requests.post(url, data=data).json()
        score = r.get("score_tag","NEU")
        return {"P+":1.0,"P":0.5,"NEU":0,"N":-0.5,"N+":-1.0}.get(score,0)
    except: return 0

def twitter_sentiment(symbol):
    texts = twitter_fetch_tweets(symbol)
    if not texts: return 0
    scores = [sentiment_score_meaningcloud(t) for t in texts]
    return round(sum(scores)/len(scores),2)

# ---------------- AI PUMP ----------------
def pump_probability(symbol):
    price, change, volume = coinmarketcap_price(symbol)
    sentiment = twitter_sentiment(symbol)
    arb = dexscreener_arb(symbol)
    arb_gain = ((arb.get('hi_price',0)-arb.get('lo_price',0))/arb.get('lo_price',1))*100 if arb else 0
    pump_score = (change*0.4)+(sentiment*20)+(arb_gain*0.4)
    pump_score = min(max(pump_score,0),100)
    return round(pump_score,2)

# ---------------- WHALE ALERTS ----------------
def whale_alerts(symbol):
    # Mock data: Replace with API calls to Ethereum/BSC/Solana explorers
    whales = []
    for chain in ["ETH","BSC","SOL"]:
        amt = random.uniform(1000,5000)
        if amt>3000: whales.append(f"{chain} whale transfer detected: {amt:.2f} {symbol}")
    return whales

# ---------------- COMMAND HANDLERS ----------------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Mega Crypto Bot!", reply_markup=main_menu_keyboard())

async def price_handler(update, ctx):
    symbol = (ctx.args[0].upper() if ctx.args else "BTC")
    price, change, _ = coinmarketcap_price(symbol)
    await update.message.reply_text(box(f"{symbol} Price", f"💵 ${price:.4f}\n📈 24h: {change:+.2f}%"))

async def arb_handler(update, ctx):
    symbol = (ctx.args[0].upper() if ctx.args else "BTC")
    arb = dexscreener_arb(symbol)
    if not arb:
        await update.message.reply_text("No live DEX data found.")
        return
    gain = ((arb['hi_price']-arb['lo_price'])/arb['lo_price'])*100
    txt = f"Buy: {arb['lo_price']:.4f} Sell: {arb['hi_price']:.4f} → Arb: {gain:.2f}%"
    await update.message.reply_text(box(f"{symbol} DEX Arbitrage", txt))

async def sentiment_handler(update, ctx):
    symbol = (ctx.args[0].upper() if ctx.args else "BTC")
    score = twitter_sentiment(symbol)
    await update.message.reply_text(box(f"{symbol} Twitter Sentiment", f"Score: {score}"))

async def pump_handler(update, ctx):
    symbol = (ctx.args[0].upper() if ctx.args else "BTC")
    score = pump_probability(symbol)
    await update.message.reply_text(box(f"{symbol} Pump Probability", f"🌟 {score}%"))

async def portfolio_handler(update, ctx):
    user_id = update.effective_user.id
    pf = get_portfolio(user_id)
    if not pf: await update.message.reply_text("Your portfolio is empty."); return
    lines = [f"{sym}: {amt}" for sym, amt in pf.items()]
    await update.message.reply_text(box("Your Portfolio", "\n".join(lines)))

async def news_handler(update, ctx):
    await update.message.reply_text("News + Macro AI analysis coming soon (can integrate crypto news APIs)")

async def whale_handler(update, ctx):
    symbol = (ctx.args[0].upper() if ctx.args else "BTC")
    alerts = whale_alerts(symbol)
    if not alerts: await update.message.reply_text("No whale activity detected."); return
    await update.message.reply_text(box(f"{symbol} Whale Alerts", "\n".join(alerts)))

# ---------------- BUTTON HANDLER ----------------
async def button_handler(update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "price": await price_handler(update,ctx)
    elif q.data == "arb": await arb_handler(update,ctx)
    elif q.data == "sentiment": await sentiment_handler(update,ctx)
    elif q.data == "pump": await pump_handler(update,ctx)
    elif q.data == "portfolio": await portfolio_handler(update,ctx)
    elif q.data == "news": await news_handler(update,ctx)
    elif q.data == "whale": await whale_handler(update,ctx)
    else: await q.edit_message_text("Feature coming soon!")

# ---------------- BACKGROUND ALERT TASK ----------------
async def alert_task(app: Application):
    while True:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT user_id FROM portfolio")
        users = [row[0] for row in c.fetchall()]
        for user_id in users:
            pf = get_portfolio(user_id)
            for sym in pf.keys():
                pump = pump_probability(sym)
                if pump>80:  # high probability
                    try:
                        await app.bot.send_message(user_id, box(f"{sym} Pump Alert", f"High pump probability: {pump}%"))
                    except: pass
        conn.close()
        await asyncio.sleep(300)  # every 5 minutes

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price_handler))
    app.add_handler(CommandHandler("arb", arb_handler))
    app.add_handler(CommandHandler("sentiment", sentiment_handler))
    app.add_handler(CommandHandler("pump", pump_handler))
    app.add_handler(CommandHandler("portfolio", portfolio_handler))
    app.add_handler(CommandHandler("news", news_handler))
    app.add_handler(CommandHandler("whale", whale_handler))

    # Buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # Background alerts
    loop = asyncio.get_event_loop()
    loop.create_task(alert_task(app))

    logger.info("🚀 Mega Crypto Bot is running!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
