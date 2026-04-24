import time
import re
import requests
import datetime
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbwHHH2oB71Q70-ddp2Badrpz46pvV1Wh_tJEWFG7ugr2IApqgHgOP2z32MwIfUA3vp2/exec"
TICKERS = ["NVDA", "SPY", "QQQ", "TSLA", "MU", "AAPL"]

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
    except: return "#FFFFFF"

def scrape_ticker(page, ticker):
    # Notice: we ensure the URL includes the GEX tab and 30 DTE
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    price = get_live_price(ticker)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("table tr td", timeout=30000)
        time.sleep(10) 

        rows = page.query_selector_all("table tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            # This captures EVERY column (Date, Strike, Call GEX, Put GEX, etc.)
            v_row = [c.inner_text().strip() for c in cells]
            
            # Check if the row has data and is not just a spacer
            if len(v_row) > 1 and v_row[0] != "":
                values_table.append(v_row)
                
                # Capture the heatmap colors
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        timestamp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).strftime("%I:%M %p")

        payload = {
            "ticker": ticker,
            "price": price,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp
        }

        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
    except Exception as e:
        print(f"[{ticker}] Error: {e}")

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for ticker in TICKERS:
            scrape_ticker(page, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
