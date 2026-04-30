import os
import time
import requests
import base64
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

WEBAPP_URL = os.environ.get('WEBAPP_URL')
TICKERS = ['NVDA', 'TSLA', 'AAPL', 'AMD']

def setup_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1600,2200') # Extra height for long tables
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def main():
    if not WEBAPP_URL: return
    driver = setup_driver()
    try:
        for ticker in TICKERS:
            print(f"Refreshing {ticker}...")
            driver.get(f"https://mztrading.netlify.app/options/analyze/{ticker}?expiry=7")
            time.sleep(18) # Animation buffer
            
            # 1. Capture Full Screen
            full_path = f"full_{ticker}.png"
            driver.save_screenshot(full_path)
            
            # 2. Precision Crop
            # Top=60: Captures Price/Sync | Bottom=1900: Captures Table
            # Left=280: Removes sidebar junk
            img = Image.open(full_path)
            chart_img = img.crop((280, 60, 1550, 1900)) 
            crop_path = f"{ticker}_final.png"
            chart_img.save(crop_path)

            # 3. Base64 & Send
            with open(crop_path, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode('utf-8')

            payload = {"ticker": ticker, "imageData": b64_string}
            res = requests.post(WEBAPP_URL, json=payload, timeout=40)
            print(f"Sent {ticker}: {res.text}")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
