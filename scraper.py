import time
import datetime
import re
import requests
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
#SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzS2BQwPB7Cx_-M9_tpNAjo_rbhD7Dbp0xt4OeEXftcXREl-hq7VHBn5yfT3sdxNHTHXg/exec"
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbxkVyQZ0D-oE91cOoi3iNPRvI4uJ2WGl9luW9GaJWChm3ocSOR222ifYh4-dZZhqT3ctw/exec"
TICKERS = ["^SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]

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
    # Create a fresh page for each ticker to prevent cache bloat
    page = context.new_page()
    page.set_default_timeout(30000)
    
    chart_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&expiry=7"
    data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    
    print(f"[{ticker}] Starting...")
    price = get_live_price(ticker)
    
    try:
        # --- 1. CAPTURE 7D CHART (FAST) ---
        page.goto(chart_url, wait_until="commit") # "commit" is the fastest possible trigger
        time.sleep(5) 
        chart_base64 = ""
        chart_element = page.locator(".recharts-responsive-container, #gex-chart").first
        if chart_element.is_visible():
            chart_base64 = base64.b64encode(chart_element.screenshot()).decode('utf-8')

        # --- 2. CAPTURE 30D HEATMAP DATA ---
        page.goto(data_url, wait_until="domcontentloaded")
        page.wait_for_selector("table", timeout=15000)
        time.sleep(3) 

        rows = page.query_selector_all("table tr")
        values_table, colors_table = [], []
        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            v_row = [c.inner_text().strip() for c in cells]
            if v_row and v_row[0] != "":
                values_table.append(v_row)
                colors_table.append([rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells])

        # --- 3. SEND TO GOOGLE ---
        timestamp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).strftime("%I:%M %p")
        payload = {
            "ticker": ticker, "values": values_table, "colors": colors_table,
            "updated": timestamp, "price": price, "chart_img": chart_base64
        }
        
        # Adding a timeout to the post request so it doesn't hang the whole script
        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=15)
        print(f"[{ticker}] Updated.")

    except Exception as e:
        print(f"[{ticker}] Skipped due to error: {e}")
    finally:
        page.close() # CRITICAL: Close the page to free up memory

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Using a mobile-ish user agent often bypasses heavy desktop tracking scripts
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
            time.sleep(1) # Small breather
        browser.close()

if __name__ == "__main__":
    run_main()
