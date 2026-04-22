import time
import re
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment

# --- CONFIGURATION ---
TICKERS = ["SPY", "QQQ", "MU","NVDA", "SNDK", "AAOI", "ALAB", "TSLA"]
BASE_URL = "https://mztrading.netlify.app/options/analyze/{}?dgextab=GEX&dte=30&showHeatmap=true"
INTERVAL = 900 
FILENAME = "Market_GEX_Heatmaps.xlsx"

# Dictionary to track timestamps in memory for the console output
status_tracker = {ticker: "Not yet fetched" for ticker in TICKERS}

def rgb_to_hex(rgb_str):
    try:
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            return '{:02X}{:02X}{:02X}'.format(int(nums[0]), int(nums[1]), int(nums[2]))
        return "FFFFFF"
    except:
        return "FFFFFF"

def update_summary_sheet(wb):
    """Creates a 'Summary' tab with all tickers and their last fetch times."""
    if "Summary" in wb.sheetnames:
        ws = wb["Summary"]
        wb.remove(ws)
    
    ws = wb.create_sheet("Summary", 0) # Make it the first tab
    ws.append(["Ticker", "Last Successful Fetch"])
    
    # Style the header
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for ticker, timestamp in status_tracker.items():
        ws.append([ticker, timestamp])
    
    # Auto-adjust column width
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 25

def scrape_ticker_to_sheet(page, ticker, workbook):
    url = BASE_URL.format(ticker)
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("table", timeout=20000)
        time.sleep(3) 

        if ticker in workbook.sheetnames:
            workbook.remove(workbook[ticker])
        ws = workbook.create_sheet(ticker)

        rows = page.query_selector_all("tr")
        for r_idx, row in enumerate(rows, start=1):
            cells = row.query_selector_all("td, th")
            for c_idx, cell in enumerate(cells, start=1):
                text = cell.inner_text().strip()
                bg_color = cell.evaluate("el => window.getComputedStyle(el).backgroundColor")
                excel_cell = ws.cell(row=r_idx, column=c_idx, value=text)
                hex_color = rgb_to_hex(bg_color)
                if hex_color not in ["000000", "FFFFFF"]:
                    excel_cell.fill = PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
        
        # Update our tracker with current time
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_tracker[ticker] = now_str
        
        # Add timestamp to the specific ticker sheet as well
        ws.cell(row=len(rows) + 2, column=1, value=f"Updated: {now_str}")
        print(f"Successfully fetched {ticker} at {now_str}")

    except Exception as e:
        status_tracker[ticker] = f"Error: {str(e)[:30]}..."
        print(f"Failed to fetch {ticker}: {e}")

# ... (Keep all your imports and helper functions like rgb_to_hex)

def run_once():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        #page = browser.new_page()
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        page = context.new_page(user_agent=user_agent)

        # Try to load existing workbook to keep history, or create new
        try:
            from openpyxl import load_workbook
            wb = load_workbook(FILENAME)
        except:
            wb = Workbook()

        # ... (Your existing scrape logic for the tickers) ...

        update_summary_sheet(wb)
        wb.save(FILENAME)
        browser.close()

if __name__ == "__main__":
    run_once() # Just run it once; GitHub will trigger it again in 15 mins
