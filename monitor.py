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
    if not title: return False
    t = title.lower()
    
    if not re.search(STABLES_REGEX, title, re.IGNORECASE):
        return False
        
    if not any(k in t for k in EARN_KEYWORDS):
        return False

    percents = re.findall(r"(\d+(?:\.\d+)?)\s*%", t)
    if percents:
        values = [float(x) for x in percents]
        if max(values) < MIN_APR:
            return False 

    return True

# --- FETCHER ---
def fetch_feed():
    news = []
    s = requests.Session()
    s.headers.update({'User-Agent': USER_AGENT})

    def safe_get(url):
        try: 
            r = s.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return {} 

    # 1. BINANCE
    d = safe_get(URLS['Binance 🔶'])
    # Безопасное извлечение: (d.get('data') OR {}) -> .get('articles') OR []
    data_block = d.get('data') or {}
    articles = data_block.get('articles') or []
    for x in articles:
        news.append({"s": "Binance 🔶", "id": f"bin_{x['code']}", "t": x['title'], "u": f"https://www.binance.com/en/support/announcement/{x['code']}"})

    # 2. BYBIT
    d = safe_get(URLS['Bybit ⚫️'])
    res = d.get('result') or {}
    items = res.get('list') or []
    for x in items:
        news.append({"s": "Bybit ⚫️", "id": f"by_{x['id']}", "t": x['title'], "u": x['url']})

    # 3. KUCOIN
    d = safe_get(URLS['KuCoin 🟢'])
    data_block = d.get('data') or {}
    items = data_block.get('items') or []
    for x in items:
        news.append({"s": "KuCoin 🟢", "id": f"ku_{x['id']}", "t": x['title'], "u": f"https://www.kucoin.com/announcement/{x['id']}"})

    # 4. HTX
    d = safe_get(URLS['HTX 🔥'])
    data_block = d.get('data') or {}
    items = data_block.get('list') or []
    for x in items:
        news.append({"s": "HTX 🔥", "id": f"htx_{x['id']}", "t": x['title'], "u": f"https://www.htx.com/support/en-us/detail/{x['id']}"})

    # 5. BITGET
    d = safe_get(URLS['Bitget 🔵'])
    data_list = d.get('data')
    if isinstance(data_list, list):
        for x in data_list:
            news.append({"s": "Bitget 🔵", "id": f"bg_{x['annId']}", "t": x['annTitle'], "u": x['annUrl']})
            
    # 6. MEXC
    d = safe_get(URLS['MEXC 🌊'])
    data_block = d.get('data') or {}
    items = data_block.get('result') or []
    for x in items:
        news.append({"s": "MEXC 🌊", "id": f"mx_{x['id']}", "t": x['title'], "u": f"https://www.mexc.com/support/articles/{x['id']}"})

    # 7. GATE
    try:
        d = s.get(URLS['Gate.io 🚪'], timeout=5).json()
        if isinstance(d, list):
            for x in d:
                if 'title' in x:
                    news.append({"s": "Gate.io 🚪", "id": f"gate_{x['id']}", "t": x['title'], "u": f"https://www.gate.io/article/{x['id']}"})
    except: pass

    # 8. BITMART
    d = safe_get(URLS['BitMart Ⓜ️'])
    data_bm = d.get('data') or {}
    # BitMart иногда возвращает data как list, иногда как dict
    if isinstance(data_bm, dict):
        items = data_bm.get('news') or []
        for x in items:
            news.append({"s": "BitMart Ⓜ️", "id": f"bm_{x['id']}", "t": x['title'], "u": x['url']})

    # 9. ASCENDEX
    d = safe_get(URLS['AscendEX 🚀'])
    data_block = d.get('data') or {}
    items = data_block.get('data') or []
    for x in items:
        news.append({"s": "AscendEX 🚀", "id": f"asc_{x['_id']}", "t": x['title'], "u": f"https://ascendex.com/en/support/articles/{x['_id']}"})

    # 10. BINGX
    d = safe_get(URLS['BingX 🟦'])
    data_block = d.get('data') or {}
    items = data_block.get('list') or []
    for x in items:
         news.append({"s": "BingX 🟦", "id": f"bing_{x['id']}", "t": x['title'], "u": f"https://bingx.com/en-us/support/articles/{x['id']}"})

    return news

# --- MAIN ---
def main():
    print(f"🚀 Scanning {len(URLS)} Exchanges...")
    
    try:
        seen = load_db()
    except Exception as e:
        print(f"DB Error: {e}")
        seen = []
    
    try:
        fresh = fetch_feed()
    except Exception as e:
        print(f"Global Fetch Error: {e}")
        fresh = []

    print(f"Found {len(fresh)} total news items.")

    new_seen = list(seen)
    posted = 0

    for item in reversed(fresh):
        if item['id'] in seen: continue
        
        if is_gem(item['t']):
            msg = f"💎 *{item['s']} Earn Alert*\n\n{item['t']}\n\n👉 [Open Link]({item['u']})"
            send_tg(msg)
            print(f"✅ SENT: {item['t']}")
            posted += 1
            time.sleep(1)
        
        new_seen.append(item['id'])

    if len(new_seen) > len(seen):
        save_db(new_seen)
        print(f"Update complete. Sent: {posted}")
    else:
        print("No new relevant alerts.")

if __name__ == "__main__":
    main()
