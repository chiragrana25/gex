import time
import datetime
import re
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
# Paste your Google Apps Script Web App URL (the one ending in /exec)
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzDwiNbc40nVER-q9FW9uy0SE7motbJt0jb46c7JCJCNcmKrjWXUqy6SGRD8mjF8oRM7g/exec"

TICKERS = ["SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "ALAB", "TSLA"]

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
    
    try:
        # Navigate and wait for content
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("table", timeout=30000)
        
        # Give JS a moment to apply heatmap colors
        time.sleep(5)

        rows = page.query_selector_all("tr")
        values_table = []
        colors_table = []

        for row in rows:
            cells = row.query_selector_all("td, th")
            v_row = []
            c_row = []
            
            for cell in cells:
                # Get the text
                v_row.append(cell.inner_text().strip())
                
                # Get the visual color
                bg = cell.evaluate("el => window.getComputedStyle(el).backgroundColor")
                c_row.append(rgb_to_hex(bg))
            
            if v_row:
                values_table.append(v_row)
                colors_table.append(c_row)
                
        # Get the current time in EST
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4) # Currently EDT
        timestamp = now_est.strftime("%Y-%m-%d %I:%M:%S %p EST")
        
        # Prepare the data packet for Google Sheets
        payload = {
            "ticker": ticker,
            "values": values_table,
            "colors": colors_table
            "updated": timestamp
        }

        # Send to Google Apps Script
        response = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Status: {response.text}")

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

        browser.close()

if __name__ == "__main__":
    run_main()
