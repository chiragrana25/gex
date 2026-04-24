import time
import datetime
import re
import requests
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbyNk7VGZKxAiPli-L8mrDHaEq1fJbjhbpNJgJmxxXDT-6CuuRN7WdU-HJv8dpo9Wf4nLQ/exec"

TICKERS = ["SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "ALAB", "TSLA", "MSFT", "CRWV", "RDDT", "AMD", "PANW", "ASTS", "UNH"]

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
    
    # Get price first so it's always defined
    price = get_live_price(ticker)
    
    try:
        # Navigate and wait for content
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("table", timeout=30000)
        
        # Give JS extra time to load the dynamic GEX numbers and heatmap
        time.sleep(8)

        rows = page.query_selector_all("tr")
        values_table = []
        colors_table = []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            v_row = []
            c_row = []
            
            for cell in cells:
                # Get the text (This includes the Date if present in the first column)
                v_row.append(cell.inner_text().strip())
                
                # Get the visual color
                bg = cell.evaluate("el => window.getComputedStyle(el).backgroundColor")
                c_row.append(rgb_to_hex(bg))
            
            # Only add rows that actually contain data
            if v_row and v_row[0] != "":
                values_table.append(v_row)
                colors_table.append(c_row)
                
        # Get the current time in EST/EDT
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4) # Currently EDT
        timestamp = now_est.strftime("%I:%M %p")
        
        # Prepare the data packet for Google Sheets
        payload = {
            "ticker": ticker,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp,
            "price": price
        }

        # Send to Google Apps Script
        response = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Status: {response.text} | Price: {price}")

    except Exception as e:
        print(f"[{ticker}] Error encountered: {e}")

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
