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
        return f"{stock.fast_info['last_price']:.2f}"
    except: return "N/A"

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2])) if len(nums) >= 3 else "#FFFFFF"
    except: return "#FFFFFF"

def scrape_ticker(context, ticker):
    page = context.new_page()
    chart_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&expiry=7"
    data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    
    print(f"[{ticker}] Processing...")
    price = get_live_price(ticker)
    chart_base64 = ""
    
    try:
        # --- 1. CAPTURE 7D CHART ---
        page.goto(chart_url, wait_until="load", timeout=60000)
        # Wait for the chart container specifically
        page.wait_for_selector(".recharts-responsive-container", timeout=20000)
        time.sleep(10) 
        chart_element = page.locator(".recharts-responsive-container").first
        if chart_element:
            chart_base64 = base64.b64encode(chart_element.screenshot(type="jpeg", quality=50)).decode('utf-8')

        # --- 2. CAPTURE 30D DATA ---
        page.goto(data_url, wait_until="load", timeout=60000)
        
        # FIX: Instead of a complex function, wait for the text "Strike" to appear anywhere in the table
        page.get_by_text("Strike").first.wait_for(state="visible", timeout=30000)
        time.sleep(5) # Final settle time for dates to populate

        # Target all rows
        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            # Capture all cells (th or td)
            cells = row.query_selector_all("td, th")
            if not cells or len(cells) < 2: continue
            
            # Deep extract text to catch "sticky" or "hidden" date columns
            v_row = [c.evaluate("el => el.innerText || el.textContent").strip() for c in cells]
            
            if v_row and v_row[1]: # Ensure at least the second column has data
                values_table.append(v_row)
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        # --- 3. SEND TO GOOGLE ---
        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        payload = {
            "ticker": ticker, "values": values_table, "colors": colors_table,
            "updated": now_est.strftime("%I:%M %p"), "price": price, "chart_img": chart_base64
        }
        
        resp = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=60)
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
