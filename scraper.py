import time
import re
import requests
import datetime
import yfinance as yf  # Reliable price source
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbyVrHioce25p26HOIfBIbBkDiaEn8do5pHDO3IenRAfynOooEjiUR7kMOd5GPjT3w9MbA/exec"
TICKERS = ["SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "ALAB", "TSLA", "MSFT", "CRWV", "RDDT", "AMD", "PANW", "ASTS", "UNH"]

def get_live_price(ticker):
    """Fetches the current price from Yahoo Finance as a backup."""
    try:
        stock = yf.Ticker(ticker)
        # Get the latest price
        price = stock.fast_info['last_price']
        return f"{price:.2f}"
    except Exception as e:
        print(f"[{ticker}] YFinance Error: {e}")
        return "N/A"

def generate_recommendation(values_table):
    try:
        strikes, call_gex, put_gex = [], [], []
        
        # We assume: Col 0 = Strike, Col 1 = Call GEX, Col 2 = Put GEX
        for row in values_table[1:]:
            try:
                s = float(re.sub(r'[^\d.]', '', row[0]))
                c = float(re.sub(r'[^\d.-]', '', row[1]))
                p = float(re.sub(r'[^\d.-]', '', row[2]))
                
                strikes.append(s)
                call_gex.append(c)
                put_gex.append(p)
            except: continue

        if not strikes: return "Insufficient data."

        # Analysis for each column
        max_call_val = max(call_gex)
        call_wall = strikes[call_gex.index(max_call_val)]
        
        min_put_val = min(put_gex)
        put_wall = strikes[put_gex.index(min_put_val)]

        analysis = (
            f"CALL WALL (Resistance): ${call_wall} | "
            f"PUT WALL (Support): ${put_wall} | "
            f"BIAS: {'Bullish' if abs(max_call_val) > abs(min_put_val) else 'Bearish'}"
        )
        return analysis
    except Exception as e:
        return f"Analysis Error: {str(e)}"

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except: return "#FFFFFF"

def scrape_ticker(page, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    
    # Get price from Yahoo Finance as the base
    price = get_live_price(ticker)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # CRITICAL: Wait for the table to actually have data rows (not just headers)
        page.wait_for_selector("table tr td", timeout=30000)
        
        # Extra padding for the GEX engine to finish calculations
        time.sleep(10) 

        rows = page.query_selector_all("table tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            v_row = [c.inner_text().strip() for c in cells]
            # Only process rows that look like data (avoiding empty spacers)
            if len(v_row) > 1 and v_row[0] != "":
                values_table.append(v_row)
                
                # Get colors for the heatmap
                c_row = []
                for cell in cells:
                    bg = cell.evaluate("el => window.getComputedStyle(el).backgroundColor")
                    c_row.append(rgb_to_hex(bg))
                colors_table.append(c_row)

        # Generate Time and Recommendation
        timestamp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).strftime("%I:%M %p")
        recommendation = generate_recommendation(values_table)

        # 3. SEND PAYLOAD
        payload = {
            "ticker": ticker,
            "price": price,
            "values": values_table,
            "colors": colors_table,
            "updated": timestamp,
            "recommendation": recommendation
        }

        response = requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Status: {response.text} | Price: {price}")

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
