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
    options.add_argument('--window-size=1600,2200') 
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def main():
    if not WEBAPP_URL:
        print("CRITICAL: WEBAPP_URL secret is missing!")
        return

    driver = setup_driver()
    try:
        for ticker in TICKERS:
            print(f"Refreshing {ticker}...")
            driver.get(f"https://mztrading.netlify.app/options/analyze/{ticker}?expiry=7")
            time.sleep(18) # Wait for rendering
            
            full_path = f"full_{ticker}.png"
            driver.save_screenshot(full_path)
            
            # 1. Precision Crop
            # Reduced 'right' to 1400 to cut off excess space
            left, top, right, bottom = 280, 60, 1200, 1900
            
            img = Image.open(full_path)
            chart_img = img.crop((left, top, right, bottom))
            
            # 2. Resize logic for Google 1M pixel limit
            width, height = chart_img.size
            max_pixels = 950000
            if (width * height) > max_pixels:
                scale_factor = (max_pixels / (width * height))**0.5
                new_size = (int(width * scale_factor), int(height * scale_factor))
                chart_img = chart_img.resize(new_size, Image.LANCZOS)
                print(f"Resized {ticker} for Google limits.")

            crop_path = f"{ticker}_final.png"
            chart_img.save(crop_path, optimize=True, quality=85)

            # 3. Base64 & Send
            with open(crop_path, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode('utf-8')

            payload = {"ticker": ticker, "imageData": b64_string}
            
            # FIXED: Added 'res =' here to define the variable
            res = requests.post(WEBAPP_URL, json=payload, timeout=40)
            print(f"Sent {ticker}: {res.text}")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
