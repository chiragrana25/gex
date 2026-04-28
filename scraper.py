import time
import datetime
import requests
import json
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbzl7u-box2PecnxTqW4bhWAtjbhpGrgHAmvzfPbzuqujRODLXq7SsL_sueaz2WRyIS35w/exec"
#TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]
TICKERS = ["SPY"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return f"{stock.fast_info['last_price']:.2f}"
    except: return "N/A"

def scrape_ticker(browser, ticker):
    # We only need ONE URL now because the API data usually contains all expiries
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30"
    
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = context.new_page()
    
    print(f"[{ticker}] Intercepting Data...")
    price = get_live_price(ticker)
    
    captured_data = {"table": None}

    # INTERCEPTION LOGIC: Catch the JSON response from the server
    def handle_response(response):
        if "api" in response.url or ".json" in response.url:
            try:
                captured_data["table"] = response.json()
            except: pass

    page.on("response", handle_response)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5) # Allow background API calls to finish

        # If interception failed, fallback to a simple table scrape
        if not captured_data["table"]:
            print(f"[{ticker}] API Intercept failed, falling back to DOM scrape...")
            values = page.evaluate("() => Array.from(document.querySelectorAll('tr')).map(row => Array.from(row.querySelectorAll('td, th')).map(c => c.innerText.trim()))")
        else:
            # Format the intercepted JSON into a table for Google Sheets
            # This depends on the JSON structure of MZTrading
            values = format_json_to_table(captured_data["table"])

        now_est = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)
        payload = {
            "ticker": ticker,
            "values": values,
            "updated": now_est.strftime("%I:%M %p"),
            "price": price
        }
        
        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Sync Complete.")

    except Exception as e:
        print(f"[{ticker}] Error: {e}")
    finally:
        context.close()

def format_json_to_table(json_data):
    # This is a placeholder; you'll adjust based on the JSON keys found in MZTrading's API
    # Usually: [['Strike', 'GEX', 'DTE'], [450, 100000, 30], ...]
    return json_data if isinstance(json_data, list) else [["API Error"]]

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for ticker in TICKERS:
            scrape_ticker(browser, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
