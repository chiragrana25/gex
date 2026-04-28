import time
import datetime
import requests
import json
import yfinance as yf
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
SHEETS_BRIDGE_URL = "https://script.google.com/macros/s/AKfycbxc9kkOzOMRN_tAjobze3wgBGW0iMnFBgj7lFSyPX0QlGA0GKqXCZbzFxYWMnPnJQT_MA/exec"
#TICKERS = ["SPX", "SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "TSLA", "NBIS", "CRWV", "AMD", "PANW", "ASTS", "UNH"]
TICKERS = ["SPY"]

def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return f"{stock.fast_info['last_price']:.2f}"
    except: return "N/A"

def scrape_ticker(browser, ticker):
    url = f"https://mztrading.netlify.app/options/analyze/{ticker}?dgextab=GEX&dte=30"
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = context.new_page()
    
    print(f"[{ticker}] Intercepting network data...")
    captured_json = []

    # Listen for the background data packet
    def on_response(response):
        if "api" in response.url or "netlify.app" in response.url:
            if response.status == 200 and "json" in response.headers.get("content-type", ""):
                try:
                    captured_json.append(response.json())
                except: pass

    page.on("response", on_response)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(5) # Give the background fetch a moment

        # Fallback: If interception failed, we do a very simple table grab
        if not captured_json:
            print(f"[{ticker}] API not caught, using DOM fallback...")
            values = page.evaluate("""() => {
                const rows = Array.from(document.querySelectorAll('tr'));
                return rows.map(row => Array.from(row.querySelectorAll('td, th')).map(c => c.innerText.trim())).filter(r => r.length > 0);
            }""")
        else:
            # We take the largest JSON object found (usually the GEX table)
            data = max(captured_json, key=len)
            values = data if isinstance(data, list) else [["Data Error"]]

        payload = {
            "ticker": ticker,
            "values": values,
            "updated": (datetime.datetime.now() - datetime.timedelta(hours=4)).strftime("%I:%M %p"),
            "price": get_live_price(ticker)
        }
        
        requests.post(SHEETS_BRIDGE_URL, json=payload, timeout=30)
        print(f"[{ticker}] Sync Successful.")

    except Exception as e:
        print(f"[{ticker}] Failed: {e}")
    finally:
        context.close()

def run_main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for ticker in TICKERS:
            scrape_ticker(browser, ticker)
        browser.close()

if __name__ == "__main__":
    run_main()
