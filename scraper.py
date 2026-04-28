import time
import datetime
import re
import requests
import base64
import yfinance as yf  # Added for reliable price
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---#
#SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzS2BQwPB7Cx_-M9_tpNAjo_rbhD7Dbp0xt4OeEXftcXREl-hq7VHBn5yfT3sdxNHTHXg/exec"
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbxkVyQZ0D-oE91cOoi3iNPRvI4uJ2WGl9luW9GaJWChm3ocSOR222ifYh4-dZZhqT3ctw/exec"
TICKERS = ["^SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    """Fetches real-time price from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        return f"{price:.2f}"
    except Exception:
        return "N/A"

def rgb_to_hex(rgb_str):
    """Converts CSS rgb() strings to Google Sheets hex format."""
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except Exception:
        return "#FFFFFF"

def scrape_ticker(context, ticker):
    # Standard 30D for the Heatmap Table
    data_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    # 7D Expiry for the Graphic Screenshot
    chart_url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&expiry=7"
    
    page = context.new_page()
    page.set_default_timeout(45000)
    print(f"[{ticker}] Processing...")
    
    price = get_live_price(ticker)
    chart_base64 = ""
    
    try:
        # --- 1. CAPTURE 7D CHART SCREENSHOT ---
        page.goto(chart_url, wait_until="networkidle")
        # Nudge the page to trigger JS chart rendering
        page.mouse.wheel(0, 300)
        
        # Look for the Recharts container
        chart_selector = ".recharts-wrapper, .recharts-responsive-container"
        try:
            page.wait_for_selector(chart_selector, state="visible", timeout=20000)
            time.sleep(5) # Wait for animation to finish
            chart_element = page.locator(chart_selector).first
            if chart_element:
                # Capture as JPEG at 60% quality to keep payload small for Google
                img_bytes = chart_element.screenshot(type="jpeg", quality=60)
                chart_base64 = base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            print(f"[{ticker}] Chart capture skipped: {e}")

        # --- 2. CAPTURE 30D HEATMAP DATA ---
        page.goto(data_url, wait_until="networkidle")
        page.wait_for_selector("table th", timeout=20000)
        time.sleep(3) 

        rows = page.query_selector_all("table tr")
        values_table, colors_table = [], []
        
        for row in rows:
            # Captures 'th' and 'td' to ensure Date/DTE column is included
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            v_row = [c.inner_text().strip() for c in cells]
            if v_row and v_row[0] != "":
                values_table.append(v_row)
                # Capture background color for heatmap
                c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).backgroundColor")) for c in cells]
                colors_table.append(c_row)

        # --- 3. SEND TO GOOGLE SHEETS ---
        # Current time in EST/EDT
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4)
        timestamp = now_est.strftime("%I:%M %p")

        payload = {
            "ticker": ticker,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp,
            "price": price,
            "chart_img": chart_base64
        }

        # Increased timeout for Google side image processing
        response = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=60)
        print(f"[{ticker}] Sync: {response.text}")

    except Exception as e:
        print(f"[{ticker}] Global Failure: {e}")
    finally:
        page.close() # Important to prevent memory leaks

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Optimized viewport for clear chart captures
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
            time.sleep(2) # Prevent rate limiting
            
        browser.close()

if __name__ == "__main__":
    run_main()
