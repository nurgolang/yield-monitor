import feedparser
import requests
import json
import os
import sys
import re
import time
from datetime import datetime

# --- CONFIG ---
STABLES_REGEX = r"(USDT|USDC|BUSD|DAI|FDUSD|USDE|USDD|PYUSD|TUSD|USD1|USDG|EURT|EURQ|EURI|AEUR|\$U|\bU\b)"

EARN_KEYWORDS = [
    "apr", "apy", "yield", "earn", "interest", "flexible", "locked", "staking", "lending", "simple earn", "wealth", "vault",
    "launchpool", "launchpad", "kickstarter", "startup", "gempool", "poolx", "primeearn", "super earn", "megadrop", "hodl & earn"
]

MIN_APR = 10.0
DB_FILE = "seen_news.json"

# --- RSS FEEDS (Official & Aggregated) ---
# Мы используем RSS блогов, так как API закрыты Cloudflare
RSS_URLS = {
    "Binance 🔶": "https://www.binance.com/en/support/announcement/c-48?format=rss", # Official (часто скрыт, но попробуем)
    "Kraken 🐙": "https://blog.kraken.com/feed",
    "KuCoin 🟢": "https://www.kucoin.com/news/rss", 
    "Bitfinex 🔵": "https://www.bitfinex.com/posts.rss",
    "Coinbase 🟦": "https://www.coinbase.com/blog/feed.xml",
    "Gate.io 🚪": "https://www.gate.io/rss/blog",
    "Gemini ♊️": "https://www.gemini.com/blog/rss",
    "Poloniex ⚪️": "https://support.poloniex.com/hc/en-us/articles.rss", # Zendesk RSS
    "BitMEX 🔴": "https://blog.bitmex.com/feed/",
    "OKX ⚫️": "https://www.okx.com/rss/learn", # Блог (не анонсы, но лучше чем ничего)
}

# --- SYSTEM ---
def get_env(name): return os.environ.get(name)
TG_TOKEN = get_env("TG_TOKEN")
TG_CHAT = get_env("TG_CHAT_ID")

def send_tg(text):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=5
        )
    except: pass

def load_db():
    if os.path.exists(DB_FILE):
        try: return json.load(open(DB_FILE))
        except: return []
    return []

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data[-500:], f)

def is_gem(title):
    if not title: return False
    t = title.lower()
    if not re.search(STABLES_REGEX, title, re.IGNORECASE): return False
    if not any(k in t for k in EARN_KEYWORDS): return False
    percents = re.findall(r"(\d+(?:\.\d+)?)\s*%", t)
    if percents:
        if max([float(x) for x in percents]) < MIN_APR: return False 
    return True

# --- FETCHER ---
def fetch_rss():
    news = []
    
    for name, url in RSS_URLS.items():
        try:
            print(f"📡 Parsing {name}...")
            feed = feedparser.parse(url)
            
            if not feed.entries:
                print(f"⚠️ Empty feed: {name}")
                continue
                
            # Берем последние 5 записей
            for entry in feed.entries[:5]:
                news.append({
                    "s": name,
                    "id": entry.link, # Ссылка уникальна
                    "t": entry.title,
                    "u": entry.link
                })
                
        except Exception as e:
            print(f"❌ Error {name}: {e}")
            
    return news

# --- MAIN ---
def main():
    print(f"🚀 RSS Scan Started...")
    seen = load_db()
    
    try:
        fresh = fetch_rss()
    except Exception as e:
        print(f"Global Error: {e}")
        fresh = []
        
    print(f"Found {len(fresh)} total RSS items.")

    new_seen = list(seen)
    posted = 0

    for item in reversed(fresh):
        if item['id'] in seen: continue
        
        if is_gem(item['t']):
            msg = f"💎 *{item['s']} Alert*\n\n{item['t']}\n\n👉 [Read Post]({item['u']})"
            send_tg(msg)
            print(f"✅ SENT: {item['t']}")
            posted += 1
        
        new_seen.append(item['id'])

    if len(new_seen) > len(seen):
        save_db(new_seen)
        print(f"Done. Sent: {posted}")
    else:
        print("No updates.")

if __name__ == "__main__":
    main()
