import os, datetime, re, requests, time, random
import yfinance as yf
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

WEBAPP_URL = os.environ.get('WEBAPP_URL')
TICKERS = ['SPX', 'SPY', 'QQQ', 'IWM', 'NVDA', 'MU', 'SNDK', 'WDC', 'AAPL', 'AMD',
           'CRWV', 'NBIS', 'MSFT', 'QCOM', 'AAOI', 'SPCX', 'ALAB', 'ANET', 'TSLA',
           'ORCL', 'AMZN', 'MSTR', 'GOOG', 'DELL', 'BE']

# Tickers with large/complex options chains that reliably need more time.
HEAVY_TICKERS = {'SPX', 'NVDA', 'AAPL', 'AMD', 'MSFT', 'TSLA', 'AMZN', 'ORCL', 'ANET', 'ALAB', 'NBIS', 'GOOG'}

MAX_ATTEMPTS = 3
BASE_TIMEOUT_MS = 90000     # for "normal" tickers
HEAVY_TIMEOUT_MS = 150000   # for known heavy chains


def rgb_to_hex(rgb_str):
    """Hardened conversion: Ignores transparency and handles empty values."""
    try:
        if not rgb_str or 'rgba(0, 0, 0, 0)' in rgb_str or 'transparent' in rgb_str:
            return "#ffffff"
        nums = re.findall(r'\d+', rgb_str)
        if len(nums) >= 3:
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
            if r == 0 and g == 0 and b == 0:
                return "#ffffff"
            return '#{:02x}{:02x}{:02x}'.format(r, g, b)
        return "#ffffff"
    except Exception:
        return "#ffffff"


def get_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.get('last_price') or t.fast_info.get('lastPrice')
        return f"{price:.2f}" if price else "N/A"
    except Exception:
        return "N/A"


def wait_for_table_ready(page, timeout_ms):
    """
    More robust hydration check than a hardcoded cell index.
    Waits until:
      1. There are a reasonable number of table cells on the page, AND
      2. At least half of the *last* row's cells contain a digit
         (the last row is the most reliable indicator that rendering
         has actually completed, rather than a fixed index that may
         not exist / may not be numeric for every ticker's layout).
    Falls back gracefully if the table structure differs slightly.
    """
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('tr');
            if (rows.length < 2) return false;

            const lastRow = rows[rows.length - 1];
            const cells = lastRow.querySelectorAll('td, th');
            if (cells.length === 0) return false;

            let numericCount = 0;
            cells.forEach(c => {
                if (/[0-9]/.test(c.innerText)) numericCount++;
            });

            const totalCells = document.querySelectorAll('td').length;
            return totalCells > 20 && numericCount >= Math.ceil(cells.length / 2);
        }""",
        timeout=timeout_ms,
    )


def scrape_data(context, ticker, attempt=1):
    clean_ticker = ticker.replace('^', '')
    url = f"https://mztrading.netlify.app/options/analyze/{clean_ticker}?dgextab=GEX&expiry=30&dte=30&showHeatmap=true"
    timeout_ms = HEAVY_TIMEOUT_MS if clean_ticker in HEAVY_TICKERS else BASE_TIMEOUT_MS

    page = context.new_page()
    print(f"[{clean_ticker}] Starting Data Sync... (attempt {attempt}/{MAX_ATTEMPTS}, timeout {timeout_ms // 1000}s)")

    try:
        # domcontentloaded is faster/more reliable than networkidle on pages
        # with polling/analytics requests that never let the network go idle.
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(2)

        wait_for_table_ready(page, timeout_ms)
        time.sleep(3)  # let heatmap colors settle

        rows = page.query_selector_all("tr")
        values_table, colors_table = [], []

        for row in rows:
            cells = row.query_selector_all("td, th")
            if not cells:
                continue
            v_row = [c.evaluate("el => el.innerText").strip() for c in cells]
            c_row = [rgb_to_hex(c.evaluate("el => window.getComputedStyle(el).getPropertyValue('background-color')")) for c in cells]
            if v_row and any(v_row):
                values_table.append(v_row)
                colors_table.append(c_row)

        if not values_table:
            raise ValueError("Table rendered but no non-empty rows were captured")

        payload = {
            "ticker": clean_ticker,
            "values": values_table,
            "colors": colors_table,
            "price": get_live_price(ticker),
            "gex_sync": (datetime.datetime.now() - datetime.timedelta(hours=4)).strftime("%m/%d/%Y %I:%M %p"),
        }

        requests.post(WEBAPP_URL, json=payload, timeout=60)
        print(f"  Success: {clean_ticker} Heatmap Sent.")
        return True

    except (PWTimeout, Exception) as e:
        print(f"  Failed {clean_ticker} (attempt {attempt}): {e}")

        # Save a screenshot on the final failed attempt so you can see
        # what the page actually looked like when it timed out.
        if attempt >= MAX_ATTEMPTS:
            try:
                os.makedirs("failures", exist_ok=True)
                page.screenshot(path=f"failures/{clean_ticker}_fail.png", full_page=True)
            except Exception:
                pass

        return False

    finally:
        page.close()


def scrape_with_retry(context, ticker):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if scrape_data(context, ticker, attempt):
            return
        if attempt < MAX_ATTEMPTS:
            backoff = 3 * attempt + random.uniform(0, 2)
            time.sleep(backoff)
    print(f"  Giving up on {ticker} after {MAX_ATTEMPTS} attempts.")


def main():
    if not WEBAPP_URL:
        return print("Error: WEBAPP_URL Secret missing.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})

        for ticker in TICKERS:
            scrape_with_retry(context, ticker)
            # Small randomized delay between tickers to avoid looking like
            # a rapid-fire bot to any soft rate-limiting on the target site.
            time.sleep(1 + random.uniform(0, 1.5))

        browser.close()


if __name__ == "__main__":
    main()
