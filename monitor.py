import requests
import json
import os
import sys
import re
import time
import random

# --- CONFIG ---
STABLES_REGEX = r"(USDT|USDC|BUSD|DAI|FDUSD|USDE|USDD|PYUSD|TUSD|USD1|USDG|EURT|EURQ|EURI|AEUR|\$U|\bU\b)"

EARN_KEYWORDS = [
    "apr", "apy", "yield", "earn", "interest", "flexible", "locked", "staking", "lending", "simple earn", "wealth", "vault",
    "launchpool", "launchpad", "kickstarter", "startup", "gempool", "poolx", "primeearn", "super earn", "megadrop", "hodl & earn"
]

MIN_APR = 10.0
DB_FILE = "seen_news.json"

# Ротируем User-Agents, чтобы не палиться
AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
]

# --- NEW 2026 ENDPOINTS ---
URLS = {
    # OFFICIAL PUBLIC API (Most stable)
    "Bybit ⚫️": "https://api.bybit.com/v5/announcements/index?locale=en-US&limit=10&type=latest_activities",
    "Bitget 🔵": "https://api.bitget.com/api/v2/public/announcement?limit=10&language=en_US",
    "KuCoin 🟢": "https://api.kucoin.com/api/v1/bulletins?lang=en_US&pageSize=10",
    "Mexc 🌊": "https://www.mexc.com/api/platform/announce/list_v2?pageNum=1&pageSize=10",
    
    # MOBILE / APP API (Harder to block)
    "Binance 🔶": "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list?catalogs=48&limit=10",
    "HTX 🔥": "https://www.htx.com/-/x/hbg/v1/support/fresh/announcement/list?limit=10&category=100000",
    "Gate.io 🚪": "https://www.gate.io/json_svr/query/?u=10&c=467664&type=1",
    "BitMart Ⓜ️": "https://api-cloud.bitmart.com/spot/v1/news?limit=10",
    
    # ZENDESK / HELP CENTER API (Backup)
    "BingX 🟦": "https://bingx.com/api/v1/common/help/article/list?pageId=1&pageSize=10&lang=en-us",
    "AscendEX 🚀": "https://ascendex.com/api/pro/v1/support/cms/announcements?page=1&pageSize=10",
    "Phemex 🦅": "https://phemex.com/api/phemex-support/help/articles/list?pageSize=10&pageNum=1",
    "CoinEx 🟩": "https://www.coinex.com/res/announcement/list?limit=10&lang=en_US",
    "Woo X 🟣": "https://support.woo.org/api/v2/help_center/en-us/articles.json?per_page=10",
    "Poloniex ⚪️": "https://api.poloniex.com/v2/support/announcements?limit=10"
}

# --- SYSTEM ---
def get_env(name):
    return os.environ.get(name)

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

# --- CORE ---
def fetch_feed():
    news = []
    
    for name, url in URLS.items():
        # Спим 1 сек между запросами, чтобы не ддосить
        time.sleep(1) 
        
        try:
            # Каждый раз случайный User-Agent
            headers = {
                'User-Agent': random.choice(AGENTS),
                'Accept': 'application/json',
                'Referer': 'https://google.com'
            }
            
            r = requests.get(url, headers=headers, timeout=10)
            
            if r.status_code != 200:
                print(f"⚠️ {name} -> {r.status_code}")
                continue
                
            d = r.json()
            
            # --- PARSERS ---
            
            # Binance
            if "Binance" in name:
                for x in (d.get('data') or {}).get('articles') or []:
                    news.append({"s": name, "id": f"bin_{x['code']}", "t": x['title'], "u": f"https://www.binance.com/en/support/announcement/{x['code']}"})

            # Bybit
            elif "Bybit" in name:
                for x in (d.get('result') or {}).get('list') or []:
                    news.append({"s": name, "id": f"by_{x['id']}", "t": x['title'], "u": x['url']})

            # Bitget
            elif "Bitget" in name:
                data = d.get('data')
                if isinstance(data, list):
                    for x in data:
                        news.append({"s": name, "id": f"bg_{x['annId']}", "t": x['annTitle'], "u": x['annUrl']})

            # KuCoin
            elif "KuCoin" in name:
                for x in (d.get('data') or {}).get('items') or []:
                    news.append({"s": name, "id": f"ku_{x['id']}", "t": x['title'], "u": f"https://www.kucoin.com/announcement/{x['id']}"})
            
            # Mexc
            elif "Mexc" in name:
                for x in (d.get('data') or {}).get('result') or []:
                    news.append({"s": name, "id": f"mx_{x['id']}", "t": x['title'], "u": f"https://www.mexc.com/support/articles/{x['id']}"})
            
            # HTX
            elif "HTX" in name:
                for x in (d.get('data') or {}).get('list') or []:
                    news.append({"s": name, "id": f"htx_{x['id']}", "t": x['title'], "u": f"https://www.htx.com/support/en-us/detail/{x['id']}"})
            
            # Gate
            elif "Gate" in name:
                if isinstance(d, list):
                    for x in d:
                        if 'title' in x: news.append({"s": name, "id": f"gate_{x['id']}", "t": x['title'], "u": f"https://www.gate.io/article/{x['id']}"})

            # BitMart
            elif "BitMart" in name:
                data = d.get('data')
                if isinstance(data, dict):
                    for x in data.get('news') or []:
                        news.append({"s": name, "id": f"bm_{x['id']}", "t": x['title'], "u": x['url']})

            # BingX
            elif "BingX" in name:
                for x in (d.get('data') or {}).get('list') or []:
                    news.append({"s": name, "id": f"bing_{x['id']}", "t": x['title'], "u": f"https://bingx.com/en-us/support/articles/{x['id']}"})

            # AscendEX
            elif "AscendEX" in name:
                for x in (d.get('data') or {}).get('data') or []:
                    news.append({"s": name, "id": f"asc_{x['_id']}", "t": x['title'], "u": f"https://ascendex.com/en/support/articles/{x['_id']}"})

            # Phemex
            elif "Phemex" in name:
                 for x in (d.get('data') or {}).get('rows') or []:
                    news.append({"s": name, "id": f"ph_{x['id']}", "t": x['title'], "u": f"https://phemex.com/support/{x['id']}"})

            # CoinEx
            elif "CoinEx" in name:
                for x in (d.get('data') or {}).get('list') or []:
                    news.append({"s": name, "id": f"cx_{x['id']}", "t": x['title'], "u": f"https://www.coinex.com/announcement/detail?id={x['id']}"})
            
            # Woo
            elif "Woo" in name:
                for x in d.get('articles') or []:
                    news.append({"s": name, "id": f"woo_{x['id']}", "t": x['title'], "u": x['html_url']})
            
            # Poloniex
            elif "Poloniex" in name:
                for x in d or []: # Poloniex returns list
                    if 'title' in x: news.append({"s": name, "id": f"polo_{x['id']}", "t": x['title'], "u": f"https://support.poloniex.com/hc/en-us/articles/{x['id']}"})

        except Exception as e:
            print(f"❌ {name} Error: {str(e)[:50]}")
            
    return news

# --- RUN ---
def main():
    print(f"🚀 Scanning {len(URLS)} Exchanges...")
    seen = load_db()
    fresh = fetch_feed()
    print(f"Found {len(fresh)} items.")
    
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
        print(f"Done. Sent: {posted}")
    else:
        print("No updates.")

if __name__ == "__main__":
    main()
