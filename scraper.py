import time
import datetime
import re
import requests
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---#
# Paste your Google Apps Script Web App URL (the one ending in /exec)
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbyVrHioce25p26HOIfBIbBkDiaEn8do5pHDO3IenRAfynOooEjiUR7kMOd5GPjT3w9MbA/exec"

TICKERS = ["SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "ALAB", "TSLA", "MSFT", "CRWV", "RDDT", "AMD", "PANW", "ASTS", "UNH"]

def rgb_to_hex(rgb_str):
    """Converts 'rgb(255, 0, 0)' to hex '#FF0000' for Google Sheets"""
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except:
        return "#FFFFFF"
def generate_recommendation(values_table):
    try:
        # Assuming Strike is Column 0 and GEX is Column 1
        # This logic finds the 'GEX Wall'
        strikes = []
        gex_values = []
        
        for row in values_table[1:]: # Skip header
            try:
                strike = float(row[0].replace('$', '').strip())
                gex = float(row[1].replace(',', '').strip())
                strikes.append(strike)
                gex_values.append(gex)
            except: continue

        max_gex = max(gex_values)
        min_gex = min(gex_values)
        call_wall = strikes[gex_values.index(max_gex)]
        put_wall = strikes[gex_values.index(min_gex)]

        if abs(max_gex) > abs(min_gex):
            return f"BULLISH BIAS: Major GEX Wall at {call_wall}. Look for support/resistance here. Consider Credit Spreads below {put_wall}."
        else:
            return f"BEARISH BIAS: Heavy Negative GEX at {put_wall}. Potential volatility trigger. Watch for price magnets near {call_wall}."
    except:
        return "NEUTRAL: Data insufficient for recommendation. Monitor volume at key strikes."
        
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
        recommendation = generate_recommendation(values_table)
        # Prepare the data packet for Google Sheets
        payload = {
            "ticker": ticker,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp,
            "price": price,
            "recommendation": recommendation
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
