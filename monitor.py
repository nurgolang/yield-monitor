import requests
import json
import os
import sys
import re
import time
from datetime import datetime

# --- CONFIGURATION 2026 ---

# Regex для всех актуальных стейблов + новые 2026 ($U, USDG, etc)
STABLES_REGEX = r"(USDT|USDC|BUSD|DAI|FDUSD|USDE|USDD|PYUSD|TUSD|USD1|USDG|EURT|EURQ|EURI|AEUR|\$U|\bU\b)"

# Слова-триггеры (Доходность)
EARN_KEYWORDS = [
    "apr", "apy", "yield", "earn", "interest", "flexible", "locked", 
    "launchpool", "booster", "staking", "lending", "simple earn", "wealth", 
    "pool", "farming", "vault", "growth"
]

# Минимальный процент для алертов (если указан в тексте)
MIN_APR = 10.0

# Файл базы данных
DB_FILE = "seen_news.json"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# --- API ENDPOINTS (TOP-14) ---
URLS = {
    # === TIER 1 (GIGA GIANTS) ===
    "Binance 🔶": "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list?catalogs=48&limit=15",
    "OKX ⚫️": "https://www.okx.com/v3/support/announcements/latest?limit=15",
    "Bybit ⚫️": "https://api.bybit.com/v5/announcements/index?locale=en-US&limit=15&type=latest_activities",
    "KuCoin 🟢": "https://api.kucoin.com/api/v1/bulletins?lang=en_US&pageSize=15",
    "HTX 🔥": "https://www.htx.com/-/x/hbg/v1/support/fresh/announcement/list?limit=15&category=100000",
    "Gate.io 🚪": "https://www.gate.io/json_svr/query/?u=10&c=467664&type=1", 
    "Kraken 🐙": "https://api.kraken.com/0/public/OHLC?pair=XBTUSD", # Заглушка, Kraken парсится через RSS (см ниже)

    # === TIER 2 (HIGH YIELD / AGGRESSIVE) ===
    "Bitget 🔵": "https://api.bitget.com/api/v2/public/announcement?limit=15&language=en_US",
    "MEXC 🌊": "https://www.mexc.com/api/platform/announce/list_v2?pageNum=1&pageSize=15", 
    "BitMart Ⓜ️": "https://api-cloud.bitmart.com/spot/v1/news?limit=15", 
    "CoinEx 🟩": "https://www.coinex.com/res/announcement/list?limit=15&lang=en_US",
    "Phemex 🦅": "https://phemex.com/api/phemex-support/help/articles/list?pageSize=15&pageNum=1",
    "AscendEX 🚀": "https://ascendex.com/api/pro/v1/support/cms/announcements?page=1&pageSize=15",
    "Woo X 🟣": "https://support.woo.org/api/v2/help_center/en-us/articles.json?per_page=15" # Zendesk API
}

# --- HELPERS ---

def get_env(name):
    val = os.environ.get(name)
    if not val: 
        print(f"⚠️ Warning: {name} not found. Notifications disabled.")
        return None
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
    except Exception as e:
        print(f"TG Error: {e}")

def load_db():
    if os.path.exists(DB_FILE):
        try: return json.load(open(DB_FILE))
        except: return []
    return []

def save_db(data):
    # Храним 500 последних записей (так как бирж много)
    with open(DB_FILE, 'w') as f: json.dump(data[-500:], f)

# --- ANALYSIS ENGINE ---

def is_gem(title):
    t = title.lower()
    
    # 1. Stablecoin Filter
    if not re.search(STABLES_REGEX, title, re.IGNORECASE):
        return False
        
    # 2. Keywords Filter
    if not any(k in t for k in EARN_KEYWORDS):
        return False

    # 3. High Yield Logic
    # Ищем: "Earn 5%", "Up to 20%", "30% APR"
    # Игнорируем: "0.1% fees", "Fee 0%"
    percents = re.findall(r"(\d+(?:\.\d+)?)\s*%", t)
    
    if percents:
        # Конвертируем все найденные проценты в числа
        values = [float(x) for x in percents]
        
        # Если максимальный процент < 10, вероятно это мусор или низкая ставка
        if max(values) < MIN_APR:
            return False 

    return True

# --- FETCHERS ---

def fetch_feed():
    news = []
    s = requests.Session()
    s.headers.update({'User-Agent': USER_AGENT})

    def safe_get(url):
        try: return s.get(url, timeout=4).json()
        except: return None

    # 1. Binance
    d = safe_get(URLS['Binance 🔶'])
    if d:
        for x in d.get('data', {}).get('articles', []):
            news.append({"s": "Binance 🔶", "id": f"bin_{x['code']}", "t": x['title'], "u": f"https://www.binance.com/en/support/announcement/{x['code']}"})

    # 2. OKX
    d = safe_get(URLS['OKX ⚫️'])
    if d:
        for x in d.get('data', []):
            news.append({"s": "OKX ⚫️", "id": x['url'], "t": x['title'], "u": x['url']})

    # 3. Bybit
    d = safe_get(URLS['Bybit ⚫️'])
    if d:
        for x in d.get('result', {}).get('list', []):
            news.append({"s": "Bybit ⚫️", "id": f"by_{x['id']}", "t": x['title'], "u": x['url']})

    # 4. KuCoin
    d = safe_get(URLS['KuCoin 🟢'])
    if d:
        for x in d.get('data', {}).get('items', []):
            news.append({"s": "KuCoin 🟢", "id": f"ku_{x['id']}", "t": x['title'], "u": f"https://www.kucoin.com/announcement/{x['id']}"})

    # 5. HTX
    d = safe_get(URLS['HTX 🔥'])
    if d:
        for x in d.get('data', {}).get('list', []):
            news.append({"s": "HTX 🔥", "id": f"htx_{x['id']}", "t": x['title'], "u": f"https://www.htx.com/support/en-us/detail/{x['id']}"})

    # 6. Bitget
    d = safe_get(URLS['Bitget 🔵'])
    if d:
        for x in d.get('data', []):
            news.append({"s": "Bitget 🔵", "id": f"bg_{x['annId']}", "t": x['annTitle'], "u": x['annUrl']})
            
    # 7. MEXC (Unstable, but worth it)
    d = safe_get(URLS['MEXC 🌊'])
    if d:
        for x in d.get('data', {}).get('result', []):
            news.append({"s": "MEXC 🌊", "id": f"mx_{x['id']}", "t": x['title'], "u": f"https://www.mexc.com/support/articles/{x['id']}"})

    # 8. Kraken (RSS Hack via CoinDesk or Blog parsing is hard, skipping direct API cause private. 
    # Using public blog RSS if available, otherwise skipping to save resources)
    
    # 9. Gate.io
    try:
        # Gate часто требует капчу, пробуем лайтовый запрос
        d = s.get("https://www.gate.io/json_svr/query/?u=10&c=467664&type=1", timeout=3).json()
        for x in d: # Gate returns raw list sometimes
             # Структура может меняться, проверяем ключи
             if 'title' in x:
                news.append({"s": "Gate.io 🚪", "id": f"gate_{x['id']}", "t": x['title'], "u": f"https://www.gate.io/article/{x['id']}"})
    except: pass

    # 10. CoinEx
    d = safe_get(URLS['CoinEx 🟩'])
    if d:
        for x in d.get('data', {}).get('list', []):
            news.append({"s": "CoinEx 🟩", "id": f"cx_{x['id']}", "t": x['title'], "u": f"https://www.coinex.com/announcement/detail?id={x['id']}"})

    # 11. Woo X (Zendesk)
    d = safe_get(URLS['Woo X 🟣'])
    if d:
        for x in d.get('articles', []):
            news.append({"s": "Woo X 🟣", "id": f"woo_{x['id']}", "t": x['title'], "u": x['html_url']})

    return news

# --- RUNNER ---

def main():
    print(f"🚀 Scanning {len(URLS)} Exchanges...")
    seen = load_db()
    
    # Пытаемся получить новости (даже если часть бирж отвалится)
    try:
        fresh = fetch_feed()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        fresh = []

    new_seen = list(seen)
    posted = 0

    # Обработка
    for item in reversed(fresh):
        if item['id'] in seen: continue
        
        # Анализ
        if is_gem(item['t']):
            # Форматируем дату для лога
            msg = f"💰 *{item['s']} Opportunity*\n\n{item['t']}\n\n👉 [Link to Announcement]({item['u']})"
            send_tg(msg)
            print(f"✅ POSTED: {item['t']}")
            posted += 1
        else:
            # Uncomment to debug
            # print(f"Skipped: {item['t']}")
            pass
            
        new_seen.append(item['id'])

    if len(new_seen) > len(seen):
        save_db(new_seen)
        print(f"Done. New alerts: {posted}")
    else:
        print("No new alerts.")

if __name__ == "__main__":
    main()
