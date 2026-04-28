import time
import datetime
import requests
import json
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbz6UkSdt9v8eVTdLI99O3lRKswFhG-pfWEabovc8x24jOoO6r9ry8Egx7SlfdSV11BYIw/exec"
#TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]
TICKERS = ["SPY"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return f"{stock.fast_info['last_price']:.2f}"
    except: return "N/A"

def scrape_ticker(context, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30"
    page = context.new_page()
    print(f"[{ticker}] Waiting for data...")
    
    try:
        # 1. Load page
        page.goto(url, wait_until="load", timeout=60000)
        
        # 2. BRUTE FORCE WAIT: Wait specifically for a cell containing a "$" or a number
        # This prevents "API Error" caused by scraping an empty skeleton
        page.wait_for_selector("td:has-text('0'), td:has-text('.'), th:has-text('Strike')", timeout=45000)
        time.sleep(5) 

        # 3. DEEP EXTRACT
        # We use a JS map to ensure we get every column, including the Date
        data_payload = page.evaluate("""
            () => {
                const rows = Array.from(document.querySelectorAll('tr'));
                return rows.map(row => 
                    Array.from(row.querySelectorAll('td, th')).map(cell => cell.innerText.trim())
                ).filter(r => r.length > 0 && r[0] !== "");
            }
        """)

        # 4. SYNC
        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        payload = {
            "ticker": ticker,
            "values": data_payload,
            "updated": now_est.strftime("%I:%M %p"),
            "price": get_live_price(ticker)
        }
        
        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Sync Successful.")

    except Exception as e:
        print(f"[{ticker}] Failed: {e}")
    finally:
        page.close()

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a very specific User Agent to avoid the 'API Error' block
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        for ticker in TICKERS:
            scrape_ticker(context, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
