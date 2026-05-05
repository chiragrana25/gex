import os, datetime, re, requests, time
import yfinance as yf
from playwright.sync_api import sync_playwright

WEBAPP_URL = os.environ.get('WEBAPP_URL')
TICKERS = ['SPX','NVDA', 'SPY', 'QQQ', 'MU', 'SNDK', 'AAPL', 'AMD', 'CRWV', 'NBIS', 'MSFT', 'QCOM', 'AAOI', 'ASTS', 'RDDT', 'ALAB', 'ANET','MSTR', 'TEM','TSLA']

def rgb_to_hex(rgb_str):
    """Hardened conversion: Ignores transparency and handles empty values."""
    try:
        # If it's transparent or empty, return pure white so the sheet stays clean
        if not rgb_str or 'rgba(0, 0, 0, 0)' in rgb_str or 'transparent' in rgb_str:
            return "#ffffff"
        
        # Extract numbers
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
            
            # ANTI-BLACK FILTER: If the color is literally (0,0,0) but the site 
            # is light-themed, it's likely a rendering error. Default to white.
            if r == 0 and g == 0 and b == 0:
                return "#ffffff" 
                
            return '#{:02x}{:02x}{:02x}'.format(r, g, b)
        return "#ffffff"
    except:
        return "#ffffff"


def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get('last_price') or t.fast_info.get('lastPrice')
        return f"{price:.2f}" if price else "N/A"
    except: return "N/A"

def scrape_data(context, ticker):
    clean_ticker = ticker.replace('^', '')
    url = f"https://mztrading.netlify.app/options/analyze/{clean_ticker}?dgextab=GEX&expiry=30&dte=30&showHeatmap=true"
    page = context.new_page()
    print(f"[{clean_ticker}] Starting Data Sync...")
    
    try:
        page.goto(url, wait_until="networkidle", timeout=90000)
        
        # Anti-Stall Scroll
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(2)
        
        # Hydration Lock: Wait for table and data in cell 15
        page.wait_for_function("""() => {
            const cells = document.querySelectorAll('td');
            return cells.length > 20 && /[0-9]/.test(cells[15].innerText);
        }""", timeout=120000)
        
        time.sleep(3) # Settle colors
        
        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []
        
        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells: continue
            
            v_row = [c.evaluate("el => el.innerText").strip() for c in cells]
            # Capture heatmap background colors
            c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).getPropertyValue('background-color')")) for c in cells]
            
            if v_row and any(v_row):
                values_table.append(v_row)
                colors_table.append(c_row)
        
        payload = {
            "ticker": clean_ticker,
            "values": values_table,
            "colors": colors_table,
            "price": get_live_price(ticker),
            "gex_sync": (datetime.datetime.now() - datetime.timedelta(hours=4)).strftime("%I:%M %p")
        }
        
        requests.post(WEBAPP_URL, json=payload, timeout=60)
        print(f"  Success: {clean_ticker} Heatmap Sent.")
        
    except Exception as e:
        print(f"  Failed {clean_ticker}: {e}")
    finally:
        page.close()

def main():
    if not WEBAPP_URL: 
        return print("Error: WEBAPP_URL Secret missing.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        
        for ticker in TICKERS:
            # FIX: Ensure the parenthesis is closed here
            scrape_data(context, ticker) 
            time.sleep(1) 
            
        browser.close()

if __name__ == "__main__":
    main()
