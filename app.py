import streamlit as st
import pandas as pd
import calendar
import os

# Set the page to take up the full width of the monitor
st.set_page_config(page_title="BBQ Land Dashboard", layout="wide")

st.title("🔥 BBQ Land Unified Data Portal")

# 1. Configuration
file_configs = {
    "Sales": "Sales.csv",
    "Expenses": "Expenses.csv",
    "Cash": "Cash.csv",
    "Category": "Category.csv"
}

# Create our strict calendar reference
all_months = list(calendar.month_name)[1:]

# 2. Data Loader
@st.cache_data
def load_data():
    def clean_currency(x):
        if isinstance(x, str):
            try:
                return float(x.replace('$', '').replace(',', '').strip())
            except ValueError:
                return x
        return x

    all_dfs = []
    source_cols = {} 

    for name, path in file_configs.items():
        if not os.path.exists(path):
            continue
        
        df = pd.read_csv(path)
        
        # Standardize the time column to 'Month'
        if 'Date' in df.columns:
            df['Month'] = pd.to_datetime(df['Date'], errors='coerce').dt.month_name()
            df = df.drop(columns=['Date'])
        elif 'Month' not in df.columns:
            continue
            
        # Track which columns belong to which spreadsheet
        cols = [c for c in df.columns if c != 'Month']
        source_cols[name] = sorted(cols)
        
        # Clean the currency data
        for col in cols:
            df[col] = df[col].apply(clean_currency)
            
        all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame(), {}

    # Merge everything together
    master_df = all_dfs[0]
    for next_df in all_dfs[1:]:
        master_df = pd.merge(master_df, next_df, on='Month', how='outer')
        
    # THE FIX: Force the Month column into a strict chronological category
    master_df['Month'] = pd.Categorical(master_df['Month'], categories=all_months, ordered=True)
        
    return master_df, source_cols

# Load the data
master_df, source_cols = load_data()

if master_df.empty:
    st.error("No data found. Please ensure your 4 CSV files are in the same folder as this script.")
    st.stop()

# --- SIDEBAR CONTROLS ---
st.sidebar.header("1. Select Months")

active_months = st.sidebar.multiselect("Filter by Month:", all_months, default=[])

# THE FIX PART 2: Force the toggled items into chronological order instantly
active_months.sort(key=lambda m: all_months.index(m))

st.sidebar.divider()
st.sidebar.header("2. Select Categories")
selected_cols = []

# Generate a dropdown for each spreadsheet
for name, cols in source_cols.items():
    selected = st.sidebar.multiselect(f"--- {name.upper()} ---", cols, default=[])
    selected_cols.extend(selected)

# --- MAIN DASHBOARD AREA ---
if not active_months or not selected_cols:
    st.info("👈 Please select at least one Month and one Category from the sidebar to view your data.")
    st.stop()

# Filter Data (Because it's Categorical, .sort_values() automatically uses calendar order)
df = master_df[master_df['Month'].isin(active_months)].copy()
df = df.sort_values(by='Month')

view_df = df[['Month'] + selected_cols].copy()

# 1. Live Graph
st.subheader("📈 Financial Trends")
# Setting observed=True ensures we only graph the months you selected, not empty ones
graph_data = view_df.groupby('Month', observed=True)[selected_cols].sum()
st.line_chart(graph_data)

# 2. Detailed Data Table
st.subheader("📊 Detailed Data")

# Calculate Totals
totals = {"Month": "TOTAL"}
for col in selected_cols:
    val = pd.to_numeric(view_df[col], errors='coerce').sum()
    totals[col] = val

# Attach totals to the bottom
totals_df = pd.DataFrame([totals])
final_df = pd.concat([view_df, totals_df], ignore_index=True)

st.dataframe(final_df, use_container_width=True, hide_index=True)
