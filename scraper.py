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
    """Robust logic to analyze GEX table and suggest a play."""
    try:
        gex_values = []
        strikes = []
        
        # We start at index 1 to skip the header row
        for row in values_table[1:]:
            try:
                # Clean the strike: remove '$', ',', and spaces
                raw_strike = row[0].replace('$', '').replace(',', '').strip()
                # Clean the GEX: remove ',', and spaces
                raw_gex = row[1].replace(',', '').strip()
                
                strike = float(raw_strike)
                gex = float(raw_gex)
                
                strikes.append(strike)
                gex_values.append(gex)
            except (ValueError, IndexError):
                continue
        
        if len(gex_values) < 5: 
            return "Neutral: Insufficient data points found in table."
        
        max_val = max(gex_values)
        min_val = min(gex_values)
        max_idx = gex_values.index(max_val)
        min_idx = gex_values.index(min_val)
        
        # Simple Logic: Is the biggest wall positive or negative?
        if max_val > abs(min_val):
            return f"BULLISH: Significant Call Wall at {strikes[max_idx]}. Price often drifts toward these liquidity zones."
        else:
            return f"BEARISH: Large Put Wall at {strikes[min_idx]}. Volatility often spikes if price drops below this level."
    except Exception as e:
        return f"Neutral: Analysis error ({str(e)})"

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '#{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "#FFFFFF"
    except: return "#FFFFFF"

def scrape_ticker(page, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30&showHeatmap=true"
    print(f"[{ticker}] Starting scrape...")
    
    # 1. GET PRICE FROM YAHOO FINANCE (Very Reliable)
    price = get_live_price(ticker)
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        #page.wait_for_selector("table", timeout=30000)
        page.wait_for_selector("table tr td", timeout=30000)
        time.sleep(7)

        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            v_row, c_row = [], []
            for cell in cells:
                v_row.append(cell.inner_text().strip())
                bg = cell.evaluate("el => window.getComputedStyle(el).backgroundColor")
                c_row.append(rgb_to_hex(bg))
            if v_row:
                values_table.append(v_row)
                colors_table.append(c_row)

        # 2. GENERATE TIMESTAMP & RECOMMENDATION
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4) # EDT
        timestamp = now_est.strftime("%I:%M %p")
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
