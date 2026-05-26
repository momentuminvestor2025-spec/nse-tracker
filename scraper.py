import json
import sqlite3
import datetime
import time
from playwright.sync_api import sync_playwright

DB_NAME = "nse_52week_history.db"

def run_scraper():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Visiting NSE...")
        page.goto("https://www.nseindia.com/market-data/52-week-high-equity-market", wait_until="networkidle")
        time.sleep(5)
        
        api_url = "https://www.nseindia.com/api/live-analysis-52Week?index=high"
        
        try:
            page.goto(api_url)
            raw_text = page.locator("body").inner_text()
            response_data = json.loads(raw_text)
            records = response_data.get('data', [])
            
            if not records:
                print("No records retrieved.")
                return

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Recreate table with unique constraint if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_highs (
                    date TEXT, symbol TEXT, high_price REAL, prev_close REAL, 
                    change_percent REAL, volume INTEGER, prev_high_date TEXT,
                    UNIQUE(date, symbol)
                )
            ''')
            
            inserted_count = 0
            for item in records:
                try:
                    symbol = item.get('symbol', '').strip()
                    high_price = float(str(item.get('highPx', 0)).replace(',', ''))
                    prev_close = float(str(item.get('prevClose', 0)).replace(',', ''))
                    p_change = float(str(item.get('pChange', 0)).replace(',', ''))
                    volume = int(str(item.get('totalTradedVolume', 0)).replace(',', ''))
                    prev_high_date = item.get('prevDt', 'N/A')
                    
                    if symbol:
                        # "INSERT OR REPLACE" handles refreshes perfectly. 
                        # It updates today's data without adding a new duplicate row count!
                        cursor.execute('''
                            INSERT OR REPLACE INTO daily_highs (date, symbol, high_price, prev_close, change_percent, volume, prev_high_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (today_str, symbol, high_price, prev_close, p_change, volume, prev_high_date))
                        inserted_count += 1
                except Exception:
                    continue
                    
            conn.commit()
            print(f"Successfully processed {inserted_count} stocks for today.")
            conn.close()
            
        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_scraper()
