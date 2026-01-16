import requests
import json
import os
import sys
import re
import time

# --- CONFIG ---
STABLES_REGEX = r"(USDT|USDC|BUSD|DAI|FDUSD|USDE|USDD|PYUSD|TUSD|USD1|USDG|EURT|EURQ|EURI|AEUR|\$U|\bU\b)"

EARN_KEYWORDS = [
    "apr", "apy", "yield", "earn", "interest", "flexible", "locked", "staking", "lending", "simple earn", "wealth", "vault",
    "launchpool", "launchpad", "kickstarter", "startup", "gempool", "poolx", "primeearn", "super earn", "megadrop", "hodl & earn"
]

MIN_APR = 10.0
DB_FILE = "seen_news.json"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

URLS = {
    "Bybit ⚫️": "https://api.bybit.com/v5/announcements/index?locale=en-US&limit=15&type=latest_activities",
    "KuCoin 🟢": "https://api.kucoin.com/api/v1/bulletins?lang=en_US&pageSize=15",
    "Gate.io 🚪": "https://www.gate.io/json_svr/query/?u=10&c=467664&type=1", 
    "MEXC 🌊": "https://www.mexc.com/api/platform/announce/list_v2?pageNum=1&pageSize=15",
    "HTX 🔥": "https://www.htx.com/-/x/hbg/v1/support/fresh/announcement/list?limit=15&category=100000",
    "Bitget 🔵": "https://api.bitget.com/api/v2/public/announcement?limit=15&language=en_US",
    "Binance 🔶": "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list?catalogs=48&limit=15",
    "BitMart Ⓜ️": "https://api-cloud.bitmart.com/spot/v1/news?limit=15",
    "AscendEX 🚀": "https://ascendex.com/api/pro/v1/support/cms/announcements?page=1&pageSize=15",
    "BingX 🟦": "https://bingx.com/api/v1/common/help/article/list?pageId=1&pageSize=10&lang=en-us" 
}

# --- SYSTEM ---
def get_env(name):
    val = os.environ.get(name)
    if not val: return None
    return val

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

# --- LOGIC ---
def is_gem(title):
    t = title.lower()
    
    # 1. Stablecoin Check
    if not re.search(STABLES_REGEX, title, re.IGNORECASE):
        return False
        
    # 2. Earn Keyword Check
    if not any(k in t for k in EARN_KEYWORDS):
        return False

    # 3. APR Logic
    # Если процентов НЕТ - возвращаем True (новость интересная)
    # Если проценты ЕСТЬ - проверяем их величину
    percents = re.findall(r"(\d+(?:\.\d+)?)\s*%", t)
    if percents:
        values = [float(x) for x in percents]
        if max(values) < MIN_APR:
            return False # Процент есть, но он маленький -> False

    return True # Процентов нет, но есть кейворды -> True

# --- FETCHER ---
def fetch_feed():
    news = []
    s = requests.Session()
    s.headers.update({'User-Agent': USER_AGENT})

    def safe_get(url):
        try: 
            r = s.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            # print(f"Error fetching {url}: {e}") # Debug only
            pass
        return {} # Возвращаем пустой dict, а не None, чтобы не падать

    # 1. BINANCE
    d = safe_get(URLS['Binance 🔶'])
    for x in d.get('data', {}).get('articles', []) or []:
        news.append({"s": "Binance 🔶", "id": f"bin_{x['code']}", "t": x['title'], "u": f"https://www.binance.com/en/support/announcement/{x['code']}"})

    # 2. BYBIT
    d = safe_get(URLS['Bybit ⚫️'])
    # У Bybit иногда result=None при ошибке
    res = d.get('result') or {}
    for x in res.get('list', []) or []:
        news.append({"s": "Bybit ⚫️", "id": f"by_{x['id']}", "t": x['title'], "u": x['url']})

    # 3. KUCOIN
    d = safe_get(URLS['KuCoin 🟢'])
    for x in d.get('
