import os
import logging
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

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
                    buy_price REAL DEFAULT 0,
                    PRIMARY KEY (user_id, symbol)
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    symbol TEXT,
                    target_price REAL,
                    direction TEXT,
                    active INTEGER DEFAULT 1
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS watchlist (
                    user_id INTEGER,
                    symbol TEXT,
                    PRIMARY KEY (user_id, symbol)
                 )''')
    conn.commit()
    conn.close()

init_db()

# --- Portfolio ---
def get_portfolio(user_id):
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute("SELECT symbol, amount, buy_price FROM portfolio WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return {r[0]: {"amount": r[1], "buy_price": r[2]} for r in rows}

def update_portfolio(user_id, symbol, amount, buy_price=0):
    conn = sqlite3.connect('portfolio.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO portfolio (user_id, symbol, amount, buy_price) VALUES (?, ?, ?, ?)",
              (user_id, symbol, amount, buy_price))
    conn.commit()
    conn.close()
