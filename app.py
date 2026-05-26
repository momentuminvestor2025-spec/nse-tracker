import streamlit as st
import pandas as pd
import datetime
import sqlite3

DB_NAME = "nse_52week_history.db"

def get_today_data():
    conn = sqlite3.connect(DB_NAME)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Attempt to pull today's latest data batch
    query = f"SELECT symbol AS Symbol, high_price AS High, prev_close AS Prev_Close, change_percent AS Change_Pct, volume AS Volume, prev_high_date AS 'Previous High Date' FROM daily_highs WHERE date = '{today_str}'"
    df = pd.read_sql_query(query, conn)
    
    # Fallback to the most recent day available if data hasn't run yet today
    if df.empty:
        query_fallback = "SELECT symbol AS Symbol, high_price AS High, prev_close AS Prev_Close, change_percent AS Change_Pct, volume AS Volume, prev_high_date AS 'Previous High Date' FROM daily_highs WHERE date = (SELECT MAX(date) FROM daily_highs)"
        df = pd.read_sql_query(query_fallback, conn)
    conn.close()
    return df

def get_historical_runners(months=6):
    conn = sqlite3.connect(DB_NAME)
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=months*30)).strftime("%Y-%m-%d")
    
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
    # Filter for hits within trailing 7 calendar days
    cutoff_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    
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

# --- SCREENING & ANALYSIS ENGINE ---
def run_analytics_scanner(df_today, df_6mo):
    if df_today.empty:
        return pd.DataFrame()
    
    df_merged = pd.merge(df_today, df_6mo, on='Symbol', how='left').fillna(0)
    insights = []
    
    for _, row in df_merged.iterrows():
        triggers = []
        if row['Change_Pct'] > 4.0:
            triggers.append("Explosive Momentum (>4% Breakout)")
        if row['Volume'] > df_merged['Volume'].median() * 2:
            triggers.append("Institutional Volume Expansion")
        if row.get('Hits in Last 6 Mos', 0) > 10:
            triggers.append(f"Structural Uptrend Leader ({int(row['Hits in Last 6 Mos'])} high points)")
            
        if triggers:
            insights.append({
                "Symbol": row['Symbol'],
                "Price": f"₹{row['High']}",
                "Change %": f"{row['Change_Pct']}%",
                "Flag Reason": " & ".join(triggers)
            })
    return pd.DataFrame(insights)

# --- FRONTEND PRESENTATION LAYER ---
st.set_page_config(layout="wide", page_title="NSE Alpha Portal")
st.title("📈 Institutional NSE 52-Week High Analytics Suite")
st.caption(f"System processing time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST")

# Retrieve Datasets
df_all_today = get_today_data()
df_frequent_runners = get_historical_runners()
df_weekly_velocity = get_weekly_clusters()

if df_all_today.empty:
    st.error("🚨 Analytics engine database tracking log is currently empty. Please trigger your scraper.py pipeline.")
else:
    # Build Portal Structure via Native App Tabs
    tab1, tab2, tab3 = st.tabs([
        "🎯 Today's Complete Highs", 
        "🔥 6-Month Frequent Runners", 
        "⚡ Weekly Momentum Clusters (2+ Hits/Week)"
    ])
    
    with tab1:
        st.subheader(f"Total Market Breakouts Tracked: {len(df_all_today)} Securities")
        
        # Inject dynamic TradingView forwarding parameters
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
        st.subheader("📋 Structural Multi-Hit Leaders (180-Day Window)")
        st.write("Securities demonstrating sustained structural demand accumulation patterns over a 6-month period:")
        
        if df_frequent_runners.empty:
            st.info("Accumulating tracking depth. Multi-day breakout matches will populate here automatically.")
        else:
            df_frequent_runners['Chart Link'] = df_frequent_runners['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
            st.data_editor(
                df_frequent_runners,
                column_config={"Chart Link": st.column_config.LinkColumn("Chart Link", display_text="Launch ↗")},
                disabled=True, hide_index=True, use_container_width=True
            )
            
    with tab3:
        st.subheader("⚡ High-Velocity Weekly Repetitions")
        st.info("System Isolation Criteria: Compounding consecutive breakout velocity. These stocks have printed multiple 52-week highs inside the trailing 7-day cyclical frame.")
        
        if df_weekly_velocity.empty:
            st.warning("No stocks have logged multiple independent breakout velocity sequences yet inside this trailing 7-day window.")
        else:
            df_weekly_velocity['Chart Link'] = df_weekly_velocity['Symbol'].apply(lambda x: f"https://www.tradingview.com/chart/?symbol=NSE:{x}")
            st.data_editor(
                df_weekly_velocity,
                column_config={"Chart Link": st.column_config.LinkColumn("Chart Link", display_text="Launch ↗")},
                disabled=True, hide_index=True, use_container_width=True
            )

    # --- SIDEBAR COMPREHENSIVE AI SCANNER ---
    st.sidebar.header("🤖 Technical Insights Engine")
    st.sidebar.write("Scanning current system arrays against systemic quantitative alerts:")
    
    df_ai_alerts = run_analytics_scanner(df_all_today, df_frequent_runners)
    
    if not df_ai_alerts.empty:
        for _, alert in df_ai_alerts.iterrows():
            with st.sidebar.container(border=True):
                st.markdown(f"### **{alert['Symbol']}**")
                st.write(f"**Metrics:** Close Value at {alert['Price']} ({alert['Change %']})")
                st.caption(f"⚠️ **Scanner Flag:** {alert['Flag Reason']}")
                st.markdown(f"[Launch Terminal Chart](https://www.tradingview.com/chart/?symbol=NSE:{alert['Symbol']})")
