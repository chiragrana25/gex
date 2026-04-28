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

Here is the fully simplified, high-speed version of your project. I have stripped out the wall/peak calculations, removed the screenshot logic, and strictly focused on delivering the full table (with the Date fix) and the heatmap colors.

1. The Simplified Scraper (scraper.py)
This version focuses purely on the data table and the heatmap.

Python

import time
import datetime
import re
import requests
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "YOUR_APPS_SCRIPT_URL_HERE"
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
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    page = context.new_page()
    print(f"[{ticker}] Scraping...")
    price = get_live_price(ticker)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # DATE FIX: Wait until the first cell has text
        page.wait_for_function("""
            () => {
                const cell = document.querySelector('table th, table td');
                return cell && cell.innerText.trim().length > 0;
            }
        """, timeout=30000)
        
        time.sleep(2) 

        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            # Using evaluate to catch 'sticky' date columns
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
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
