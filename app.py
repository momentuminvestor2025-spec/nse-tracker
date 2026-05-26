import streamlit as st
import pandas as pd
import datetime
import sqlite3

DB_NAME = "nse_52week_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Enforcing UNIQUE(date, symbol) ensures a stock can only ever have ONE entry per day, preventing refresh inflation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_highs (
            date TEXT,
            symbol TEXT,
            high_price REAL,
            prev_close REAL,
            change_percent REAL,
            volume INTEGER,
            prev_high_date TEXT,
            UNIQUE(date, symbol)
        )
    ''')
    conn.commit()
    conn.close()

def get_today_data():
    conn = sqlite3.connect(DB_NAME)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Fetch ALL data logged for today
    query = f"""
        SELECT symbol AS Symbol, 
               high_price AS High, 
               prev_close AS Prev_Close, 
               change_percent AS Change_Pct, 
               volume AS Volume, 
               prev_high_date AS 'Previous High Date' 
        FROM daily_highs 
        WHERE date = '{today_str}'
    """
    df = pd.read_sql_query(query, conn)
    
    # Safe Fallback: If your automated background scraper hasn't run yet today,
    # automatically grab the ENTIRE last day recorded in your database so the page is never blank
    if df.empty:
        query_fallback = """
            SELECT symbol AS Symbol, 
                   high_price AS High, 
                   prev_close AS Prev_Close, 
                   change_percent AS Change_Pct, 
                   volume AS Volume, 
                   prev_high_date AS 'Previous High Date' 
            FROM daily_highs 
            WHERE date = (SELECT MAX(date) FROM daily_highs)
        """
        df = pd.read_sql_query(query_fallback, conn)
    conn.close()
    return df

def get_historical_runners(months=6):
    conn = sqlite3.connect(DB_NAME)
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=months*30)).strftime("%Y-%m-%d")
    
    # Since the DB now guarantees 1 row per stock per day, COUNT(*) is perfectly unique!
    query = f"""
        SELECT symbol AS Symbol, COUNT(*) AS 'Hits in Last 6 Mos'
        FROM daily_highs 
        WHERE date >= '{cutoff_date}' 
        GROUP BY symbol
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_weekly_clusters():
    conn = sqlite3.connect(DB_NAME)
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Finds stocks that hit the 52-week high on 2 or more separate days this week
    query = f"""
        SELECT symbol AS Symbol, COUNT(*) AS 'Hits This Week'
        FROM daily_highs 
        WHERE date >= '{cutoff_date}' 
        GROUP BY symbol
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# --- SCANNER ENGINE ---
def run_analytics_scanner(df_today, df_6mo):
    if df_today.empty:
        return pd.DataFrame()
    
    df_merged = pd.merge(df_today, df_6mo, on='Symbol', how='left').fillna(0)
    insights = []
    
    for _, row in df_merged.iterrows():
        triggers = []
        if row['Change_Pct'] > 3.0:
            triggers.append("High Momentum (>3% Breakout)")
        if row['Volume'] > df_merged['Volume'].median() * 1.5:
            triggers.append("Volume Surge")
        if row.get('Hits in Last 6 Mos', 0) >= 3:
            triggers.append(f"Frequent Runner ({int(row['Hits in Last 6 Mos'])} unique days)")
            
        if triggers:
            insights.append({
                "Symbol": row['Symbol'],
                "Price": f"₹{row['High']}",
                "Change %": f"{row['Change_Pct']}%",
                "Flag Reason": " & ".join(triggers)
            })
    return pd.DataFrame(insights)

# --- WEB FRONTEND ---
st.set_page_config(layout="wide", page_title="NSE Alpha Portal")
st.title("📈 Institutional NSE 52-Week High Analytics Suite")
st.caption(f"System processing time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")

init_db()

# Load real datasets
df_all_today = get_today_data()
df_frequent_runners = get_historical_runners()
df_weekly_velocity = get_weekly_clusters()

if df_all_today.empty:
    st.warning("🚨 The system tracking database is ready but waiting for data. Please run your background scraper or manual workflow on GitHub Actions to fetch the complete live list!")
else:
    # App Tabs Arrangement
    tab1, tab2, tab3 = st.tabs([
        "🎯 Today's Complete Highs", 
        "🔥 6-Month Frequent Runners", 
        "⚡ Weekly Momentum Clusters"
    ])
    
    with tab1:
        st.subheader(f"Total Market Breakouts Tracked: {len(df_all_today)} Securities")
        
        # Inject dynamic TradingView links
        df_all_today['Chart Link'] = df_all_today['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
        
        st.data_editor(
            df_all_today,
            column_config={
                "Chart Link": st.column_config.LinkColumn("Open Interactive Chart", display_text="Launch ↗")
            },
            disabled=True,
            hide_index=True,
            use_container_width=True
        )
        
    with tab2:
        st.subheader("📋 Structural Multi-Hit Leaders (Unique Days Count)")
        if df_frequent_runners.empty:
            st.info("Accumulating tracking depth. Stocks hitting new highs on multiple separate days will appear here.")
        else:
            df_frequent_runners['Chart Link'] = df_frequent_runners['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
            st.data_editor(
                df_frequent_runners,
                column_config={"Chart Link": st.column_config.LinkColumn("Chart Link", display_text="Launch ↗")},
                disabled=True, hide_index=True, use_container_width=True
            )
            
    with tab3:
        st.subheader("⚡ Separate Tab: Stocks with 2+ Hits in a Week")
        if df_weekly_velocity.empty:
            st.info("No stocks have logged hits on 2 or more separate days within the trailing 7 days.")
        else:
            df_weekly_velocity['Chart Link'] = df_weekly_velocity['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
            st.data_editor(
                df_weekly_velocity,
                column_config={"Chart Link": st.column_config.LinkColumn("Chart Link", display_text="Launch ↗")},
                disabled=True, hide_index=True, use_container_width=True
            )

    # --- AI SIDEBAR ANALYSIS ---
    st.sidebar.header("🤖 AI Analytics Engine")
    df_ai_alerts = run_analytics_scanner(df_all_today, df_frequent_runners)
    
    if not df_ai_alerts.empty:
        for _, alert in df_ai_alerts.iterrows():
            with st.sidebar.container(border=True):
                st.markdown(f"### **{alert['Symbol']}**")
                st.write(f"Price: {alert['Price']} ({alert['Change %']})")
                st.caption(f"💡 {alert['Flag Reason']}")
                st.markdown(f"[View Chart](https://www.tradingview.com/chart/?symbol=NSE:{alert['Symbol']})")
