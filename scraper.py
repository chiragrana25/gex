import time
import datetime
import re
import requests
import base64
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---#
#SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzS2BQwPB7Cx_-M9_tpNAjo_rbhD7Dbp0xt4OeEXftcXREl-hq7VHBn5yfT3sdxNHTHXg/exec"
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbwUW1uhn1ljLFJWoJX7bBS00pkwDubFuVPi8W9U0O3K4SX3Aee6576tAcXxyeGoEkMKIg/exec"
TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        return f"{price:.2f}"
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
    
    # Set a custom extra header to look more like a real browser
    page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
    
    print(f"[{ticker}] Scraping...")
    price = get_live_price(ticker)
    
    try:
        # 1. Navigate to the page
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # 2. FIXED WAIT: Wait for the specific GEX table header to appear
        # This confirms the data has actually loaded into the DOM
        page.wait_for_selector("th:has-text('GEX')", timeout=30000)
        
        # Small buffer for the rest of the rows to finish rendering
        time.sleep(5) 

        # 3. Capture all rows
        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            # Extract text using inner_text() which is more reliable for hidden columns
            v_row = [c.inner_text().strip() for c in cells]
            
            # Only add rows that actually have data (prevents empty spacer rows)
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
        # Added a real-world User Agent
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
            time.sleep(2) # Added a small gap between tickers
        browser.close()

if __name__ == "__main__":
    run_main()
