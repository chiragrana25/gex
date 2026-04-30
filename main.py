import os, datetime, re, requests, time
import yfinance as yf
from playwright.sync_api import sync_playwright

WEBAPP_URL = os.environ.get('WEBAPP_URL')
TICKERS = ['NVDA']

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        return '#{:02x}{:02x}{:02x}'.format(int(nums[0]), int(nums[1]), int(nums[2])) if len(nums) >= 3 else "#FFFFFF"
    except: return "#FFFFFF"

def scrape_data(context, ticker):
    clean_ticker = ticker.replace('^', '')
    url = f"https://mztrading.netlify.app/options/analyze/{clean_ticker}?dgextab=GEX&expiry=30&dte=30&showHeatmap=true"
    page = context.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.evaluate("window.scrollTo(0, 400)") # Wake up lazy loader
        
        # Hydration Lock
        page.wait_for_function("() => document.querySelectorAll('td').length > 20 && /[0-9]/.test(document.querySelectorAll('td')[15].innerText)", timeout=90000)
        
        rows = page.query_selector_all("tr")
        v_table, c_table = [], []
        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            v_table.append([c.evaluate("el => el.innerText").strip() for c in cells])
            c_table.append([rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells])
        
        price = yf.Ticker(ticker).fast_info.get('last_price', 'N/A')
        payload = {
            "type": "DATA_SYNC",
            "ticker": clean_ticker, "values": v_table, "colors": c_table,
            "price": f"{price:.2f}" if isinstance(price, float) else "N/A",
            "gex_sync": (datetime.datetime.now() - datetime.timedelta(hours=4)).strftime("%I:%M %p")
        }
        requests.post(WEBAPP_URL, json=payload, timeout=60)
        print(f"[{clean_ticker}] Data Synced.")
    except Exception as e: print(f"[{clean_ticker}] Error: {e}")
    finally: page.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    for t in TICKERS: scrape_data(context, t)
    browser.close()
