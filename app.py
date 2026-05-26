import streamlit as st
import pandas as pd
import datetime
import sqlite3

# --- DATABASE SETUP ---
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
            volume INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def save_today_data(df):
    """Saves today's fetched data into the historical database."""
    conn = sqlite3.connect(DB_NAME)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_highs WHERE date = ?", (today_str,))
    if cursor.fetchone()[0] == 0:
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO daily_highs (date, symbol, high_price, prev_close, change_percent, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (today_str, row['Symbol'], row['High'], row['Prev_Close'], row['Change_Pct'], row['Volume']))
        conn.commit()
    conn.close()

def get_historical_counts(months=6):
    """Fetches how many times each stock hit 52-week high in the last X months."""
    conn = sqlite3.connect(DB_NAME)
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=months*30)).strftime("%Y-%m-%d")
    
    query = f"""
        SELECT symbol AS Symbol, COUNT(*) as hit_count 
        FROM daily_highs 
        WHERE date >= '{cutoff_date}' 
        GROUP BY symbol
    """
    df_counts = pd.read_sql_query(query, conn)
    conn.close()
    
    # Fallback: If DB is empty, return a properly structured empty DataFrame
    if df_counts.empty:
        return pd.DataFrame(columns=['Symbol', 'hit_count'])
        
    return df_counts

# --- SIMULATED DATA FETCHING ---
def fetch_nse_52week_highs():
    mock_data = {
        'Symbol': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ZOMATO', 'TATASTEEL'],
        'High': [2540.0, 4120.5, 1680.0, 1710.2, 195.4, 158.2],
        'Prev_Close': [2490.0, 4100.0, 1610.0, 1705.0, 182.0, 157.0],
        'Change_Pct': [2.01, 0.50, 4.35, 0.30, 7.36, 0.76],
        'Volume': [5000000, 1200000, 3400000, 4500000, 12000000, 8000000]
    }
    return pd.DataFrame(mock_data)

# --- AUTOMATED ALGORITHMIC ANALYSIS ---
def analyze_interesting_stocks(df, df_history):
    interesting = []
    
    # Clean merge safely matching 'Symbol'
    df_merged = pd.merge(df, df_history, on='Symbol', how='left').fillna(0)
    
    for _, row in df_merged.iterrows():
        reasons = []
        if row['Change_Pct'] > 3.0:
            reasons.append("High Momentum (>3% gain)")
        if row['Volume'] > df_merged['Volume'].median() * 1.5:
            reasons.append("Volume Surge")
        if 'hit_count' in row and row['hit_count'] > 4:
            reasons.append(f"Frequent Runner ({int(row['hit_count'])} times in 6mo)")
            
        if reasons:
            interesting.append({
                "Symbol": row['Symbol'],
                "Price": row['High'],
                "Change %": f"{row['Change_Pct']}%",
                "6Mo Hits": int(row['hit_count']) if 'hit_count' in row else 0,
                "Analysis/Trigger": " & ".join(reasons)
            })
            
    return pd.DataFrame(interesting)

# --- STREAMLIT PORTAL FRONTEND ---
st.set_page_config(layout="wide", page_title="NSE 52-Week High Dashboard")
st.title("📈 NSE 52-Week High Automated Tracking Portal")
st.write(f"Data Date: {datetime.date.today().strftime('%A, %d %B %Y')}")

# Initialize and pull data safely
init_db()
df_today = fetch_nse_52week_highs()
save_today_data(df_today)
df_history_counts = get_historical_counts(months=6)

# Safe Merge Execution
if not df_history_counts.empty and 'Symbol' in df_history_counts.columns:
    df_display = pd.merge(df_today, df_history_counts, on='Symbol', how='left').fillna(0)
else:
    df_display = df_today.copy()
    df_display['hit_count'] = 0

if 'hit_count' in df_display.columns:
    df_display.rename(columns={'hit_count': 'Hits in Last 6 Mos'}, inplace=True)

# Layout Columns
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("🎯 Today's 52-Week High List")
    st.caption("💡 Use the links below to instantly view charts in a new tab.")
    
    # Native redirection URL column configuration
    df_display['Chart Link'] = df_display['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
    
    st.data_editor(
        df_display,
        column_config={
            "Chart Link": st.column_config.LinkColumn("Open Chart Tab", display_text="Open ↗")
        },
        disabled=True,
        hide_index=True
    )

with col2:
    st.subheader("🤖 Automated Analysis: Interesting Stocks")
    
    df_interesting = analyze_interesting_stocks(df_today, df_history_counts)
    
    if not df_interesting.empty:
        for idx, row in df_interesting.iterrows():
            with st.container():
                st.markdown(f"### **{row['Symbol']}** — ₹{row['Price']}")
                st.markdown(f"**Alert:** {row['Analysis/Trigger']}")
                st.markdown(f"[View Live Technicals](https://www.tradingview.com/chart/?symbol=NSE:{row['Symbol']})")
                st.divider()
    else:
        st.info("Scanning complete. No stocks broke abnormal volume or momentum triggers right now.")
