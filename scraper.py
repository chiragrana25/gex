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
        page.goto(chart_url, wait_until="networkidle", timeout=60000)
        time.sleep(15) 
        chart_selector = ".recharts-wrapper, .recharts-surface"
        try:
            if page.locator(chart_selector).first.is_visible():
                img_bytes = page.locator(chart_selector).first.screenshot(type="jpeg", quality=50)
                chart_base64 = base64.b64encode(img_bytes).decode('utf-8')
        except: pass

        # --- 2. CAPTURE 30D DATA (FORCE DATE CAPTURE) ---
        page.goto(data_url, wait_until="networkidle", timeout=60000)
        
        # Wait until the first row of the table has actual text in the first cell
        # This is the "Fix" for missing dates
        page.wait_for_function("""
            () => {
                const firstCell = document.querySelector('table tr td, table tr th');
                return firstCell && firstCell.innerText.trim().length > 0;
            }
        """, timeout=30000)

        rows = page.query_selector_all("table tr")
        values_table, colors_table = [], []

        for row in rows:
            # We explicitly grab 'th' and 'td'
            cells = row.query_selector_all("th, td")
            if not cells: continue
            
            # Extract text using a JS evaluate to ensure we get the "hidden" sticky text
            v_row = [c.evaluate("el => el.innerText").strip() for c in cells]
            
            if v_row and any(v_row):
                values_table.append(v_row)
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        # --- 3. SEND TO GOOGLE ---
        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        sync_time = now_est.strftime("%I:%M %p")

        payload = {
            "ticker": ticker, "values": values_table, "colors": colors_table,
            "updated": sync_time, "price": price, "chart_img": chart_base64
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
