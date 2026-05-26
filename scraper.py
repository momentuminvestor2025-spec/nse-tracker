# pip install playwright
# playwright install
from playwright.sync_api import sync_playwright
import json
import sqlite3
import datetime

def scrape_nse_live():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # Go to the main page first to get cookies
        page.goto("https://www.nseindia.com/market-data/52-week-high-equity-market", wait_until="networkidle")
        
        # Access the hidden API endpoint NSE uses to populate that table
        api_url = "https://www.nseindia.com/api/live-analysis-52Week?index=high"
        page.goto(api_url)
        
        # Extract raw text JSON response
        raw_json = page.locator("pre").inner_text()
        data = json.loads(raw_json)
        
        # Parse data and write to SQLite DB
        conn = sqlite3.connect("nse_52week_history.db")
        cursor = conn.cursor()
        today = datetime.date.today().strftime("%Y-%m-%d")
        
        for item in data['data']:
            cursor.execute('''
                INSERT INTO daily_highs (date, symbol, high_price, prev_close, change_percent, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (today, item['symbol'], float(item['highPx']), float(item['prevClose']), float(item['pChange']), int(item['totalTradedVolume'])))
            
        conn.commit()
        conn.close()
        browser.close()

if __name__ == "__main__":
    scrape_nse_live()