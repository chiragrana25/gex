import time
import datetime
import re
import requests
import base64
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbwxmUlmGCu4TaL1gZ7gibP5k6k3hgvI5uWJ1Dmin4oX3ZU24rPBpI8uXnVkhfMg2_iQyg/exec"
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
    page = context.new_page()
    data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    chart_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&expiry=7"
    
    print(f"[{ticker}] Processing...")
    price = get_live_price(ticker)
    
    values_table, colors_table, chart_base64 = [], [], ""

    try:
        # --- PHASE 1: DATA SCRAPE (Priority) ---
        page.goto(data_url, wait_until="networkidle", timeout=60000)
        # Wait for the table cells to actually have content (Fixes missing dates)
        page.wait_for_selector("table th, table td", timeout=20000)
        time.sleep(5) 

        rows = page.query_selector_all("tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            v_row = [c.evaluate("el => el.innerText").strip() for c in cells]
            if v_row and any(v_row):
                values_table.append(v_row)
                colors_table.append([rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells])
        
        print(f"[{ticker}] Data captured. Attempting chart...")

        # --- PHASE 2: SCREENSHOT (Secondary) ---
        try:
            page.goto(chart_url, wait_until="load", timeout=30000)
            
            # 1. FORCE THE CONTAINER TO BE VISIBLE
            # This injects CSS to ensure the chart isn't 0px tall
            page.add_style_tag(content=".recharts-responsive-container { min-height: 400px !important; min-width: 600px !important; }")
            
            # 2. TRIGGER RESIZE EVENT
            # This 'wakes up' the Recharts engine to draw the bars
            page.evaluate("window.dispatchEvent(new Event('resize'));")
            
            # 3. WAIT FOR THE ACTUAL BARS (The 'path' or 'rect' elements)
            # If the bars exist, they will be inside the .recharts-bar class
            chart_bar_selector = ".recharts-bar, .recharts-rectangle, svg"
            page.wait_for_selector(chart_bar_selector, state="visible", timeout=15000)
            
            time.sleep(5) # Let the animation finish
            
            # 4. CAPTURE
            chart_element = page.locator(".recharts-wrapper").first
            if chart_element:
                img_bytes = chart_element.screenshot(type="jpeg", quality=50)
                chart_base64 = base64.b64encode(img_bytes).decode('utf-8')
                print(f"[{ticker}] Chart captured successfully.")
        except Exception as e:
            print(f"[{ticker}] Chart skipped: {e}")

        # --- PHASE 3: SYNC ---
        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        payload = {
            "ticker": ticker, "values": values_table, "colors": colors_table,
            "updated": now_est.strftime("%I:%M %p"), "price": price, "chart_img": chart_base64
        }
        
        resp = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=45)
        print(f"[{ticker}] Sync: {resp.text}")

    except Exception as e:
        print(f"[{ticker}] Global Failure: {e}")
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
