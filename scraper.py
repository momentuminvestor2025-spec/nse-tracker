import json
import sqlite3
import datetime
import time
from playwright.sync_api import sync_playwright

DB_NAME = "nse_52week_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_highs (
            date TEXT,
            symbol TEXT,
            high_price REAL,
            prev_close REAL,
            change_percent REAL,
            volume INTEGER,
            prev_high_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def run_scraper():
    init_db()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    with sync_playwright() as p:
        # Launch browser with an organic user-agent signature
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Navigate to the main page to inherit valid session cookies natively
        print("Visiting NSE Market Watch...")
        page.goto("https://www.nseindia.com/market-data/52-week-high-equity-market", wait_until="networkidle")
        time.sleep(3)
        
        # Call the underlying API endpoint containing the entire list un-paginated
        print("Requesting full backend data JSON...")
        api_url = "https://www.nseindia.com/api/live-analysis-52Week?index=high"
        
        try:
            page.goto(api_url)
            raw_text = page.locator("body").inner_text()
            response_data = json.loads(raw_text)
            
            records = response_data.get('data', [])
            print(f"Successfully intercepted {len(records)} active breakout profiles.")
            
            if not records:
                print("No records found or session blocked.")
                return

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Clear existing entries for today if re-running to prevent key duplication
            cursor.execute("DELETE FROM daily_highs WHERE date = ?", (today_str,))
            
            for item in records:
                # Clean and parse string values from NSE data payload safely
                try:
                    symbol = item.get('symbol', '').strip()
                    high_price = float(str(item.get('highPx', 0)).replace(',', ''))
                    prev_close = float(str(item.get('prevClose', 0)).replace(',', ''))
                    p_change = float(str(item.get('pChange', 0)).replace(',', ''))
                    volume = int(str(item.get('totalTradedVolume', 0)).replace(',', ''))
                    prev_high_date = item.get('prevDt', 'N/A')
                    
                    if symbol:
                        cursor.execute('''
                            INSERT INTO daily_highs (date, symbol, high_price, prev_close, change_percent, volume, prev_high_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (today_str, symbol, high_price, prev_close, p_change, volume, prev_high_date))
                except Exception as row_err:
                    continue
                    
            conn.commit()
            print(f"Database sync finalized successfully for {today_str}.")
            conn.close()
            
        except Exception as e:
            print(f"Scraping pipeline execution failed: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_scraper()
