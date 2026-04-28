import time
import datetime
import re
import requests
import base64
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---#
#SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzS2BQwPB7Cx_-M9_tpNAjo_rbhD7Dbp0xt4OeEXftcXREl-hq7VHBn5yfT3sdxNHTHXg/exec"
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzZT1MszLLZDo6rtLgU5RJwDoUWxjbv4KD4zwbRl-9Aj-j5NPnxff21hzFpPHeHYKiEqg/exec"
TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return f"{stock.fast_info['last_price']:.2f}"
    except:
        return "N/A"

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except:
        return "#FFFFFF"

def scrape_ticker(context, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    page = context.new_page()
    print(f"[{ticker}] Scraping...")
    
    price = get_live_price(ticker)
    
    try:
        # Navigate and wait for the network to go quiet (data loaded)
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Give the JS 5 seconds to fill the table cells
        time.sleep(5) 

        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            # Capture both headers (th) and data (td) to ensure Dates are included
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            # Using evaluate(innerText) is the key to catching 'sticky' columns like Dates
            v_row = [c.evaluate("el => el.innerText").strip() for c in cells]
            
            if v_row and any(v_row):
                values_table.append(v_row)
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        payload = {
            "ticker": ticker, 
            "values": values_table, 
            "colors": colors_table,
            "updated": now_est.strftime("%I:%M %p"), 
            "price": price
        }
        
        resp = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Sync: {resp.text}")

    except Exception as e:
        print(f"[{ticker}] Error: {e}")
    finally:
        page.close()

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Standard desktop user agent
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
