import time
import datetime
import re
import requests
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzS2BQwPB7Cx_-M9_tpNAjo_rbhD7Dbp0xt4OeEXftcXREl-hq7VHBn5yfT3sdxNHTHXg/exec"

TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    """Fetches the current price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        return f"{price:.2f}"
    except:
        return "N/A"

def rgb_to_hex(rgb_str):
    """Converts 'rgb(255, 0, 0)' to hex '#FF0000' for Google Sheets"""
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except:
        return "#FFFFFF"

def scrape_ticker(page, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    print(f"[{ticker}] Starting scrape...")
    
    price = get_live_price(ticker)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("table", timeout=30000)
        time.sleep(10) 

        # We target ALL rows in the main table body and header
        rows = page.query_selector_all("table tr")
        values_table = []
        colors_table = []

        for row in rows:
            # We look for both 'td' AND 'th' in every row to catch the Date/DTE column
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            # Use a simple list comprehension to get EVERY column
            v_row = [c.inner_text().strip() for c in cells]
            
            # DEBUG: Uncomment the line below to see what Python sees in your GitHub logs
            # print(f"Row data found: {v_row}")

            if v_row:
                values_table.append(v_row)
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4)
        timestamp = now_est.strftime("%I:%M %p")
        
        payload = {
            "ticker": ticker,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp,
            "price": price
        }

        response = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Status: {response.text}")

    except Exception as e:
        print(f"[{ticker}] Error: {e}")

def run_main():
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        
        # Set a realistic user agent to avoid being blocked
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for ticker in TICKERS:
            scrape_ticker(page, ticker)
            time.sleep(2) # Small gap between tickers

        browser.close()

if __name__ == "__main__":
    run_main()
