import time
import datetime
import re
import requests
import base64
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbwxmUlmGCu4TaL1gZ7gibP5k6k3hgvI5uWJ1Dmin4oX3ZU24rPBpI8uXnVkhfMg2_iQyg/exec"
TICKERS = ["SPY", "^SPX", "QQQ", "MU", "NVDA", "SNDK", "AAOI", "ALAB", "TSLA", "MSFT", "CRWV", "RDDT", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return f"{stock.fast_info['last_price']:.2f}"
    except: return "N/A"

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2])) if len(nums) >= 3 else "#FFFFFF"
    except: return "#FFFFFF"

def scrape_ticker(context, ticker):
    # Standard 30D for the Heatmap Table
    data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    # 7D for the Chart Data
    chart_data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&expiry=7"
    
    page = context.new_page()
    print(f"[{ticker}] Scraping...")
    price = get_live_price(ticker)
    
    try:
        # 1. SCRAPE 30D TABLE DATA
        page.goto(data_url, wait_until="networkidle")
        page.wait_for_selector("table", timeout=30000)
        time.sleep(3)
        values_30d = page.evaluate("() => Array.from(document.querySelectorAll('tr')).map(row => Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim()))")
        colors_30d = [] # (Keep your existing color extraction logic here)

        # 2. SCRAPE 7D CHART DATA (The New Way)
        page.goto(chart_data_url, wait_until="networkidle")
        page.wait_for_selector("table", timeout=30000)
        # We grab the 7D table data to build the chart in Sheets
        values_7d = page.evaluate("() => Array.from(document.querySelectorAll('tr')).map(row => Array.from(row.querySelectorAll('td, th')).map(c => c.textContent.trim()))")

        # 3. SYNC TO GOOGLE
        payload = {
            "ticker": ticker,
            "values": values_30d,
            "chart_data": values_7d, # Sending raw data instead of an image
            "updated": datetime.datetime.now().strftime("%I:%M %p"),
            "price": price
        }
        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=60)
        print(f"[{ticker}] Data Sent.")
    except Exception as e:
        print(f"[{ticker}] Error: {e}")
    finally:
        page.close()
            

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
