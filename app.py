import streamlit as st
import pandas as pd
import calendar
import os

st.set_page_config(page_title="BBQ Land Dashboard", layout="wide")

st.title("🔥 BBQ Land Unified Data Portal")

file_configs = {
    "Sales": "Sales.csv",
    "Expenses": "Expenses.csv",
    "Cash": "Cash.csv",
    "Category": "Category.csv"
}

all_months = list(calendar.month_name)[1:]

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
        
        try:
            df = pd.read_csv(path, encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            
            col_lower = {c.lower(): c for c in df.columns}
            
            if 'date' in col_lower:
                actual_date_col = col_lower['date']
                df['Month'] = pd.to_datetime(df[actual_date_col], errors='coerce').dt.month_name()
                df = df.drop(columns=[actual_date_col])
            elif 'month' in col_lower:
                actual_month_col = col_lower['month']
                if actual_month_col != 'Month':
                    df = df.rename(columns={actual_month_col: 'Month'})
            else:
                continue
                
            cols = [c for c in df.columns if c != 'Month']
            source_cols[name] = sorted(cols)
            
            for col in cols:
                df[col] = df[col].apply(clean_currency)
                
            all_dfs.append(df)
            
        except Exception:
            pass

    if not all_dfs:
        return pd.DataFrame(), {}

    master_df = all_dfs[0]
    for next_df in all_dfs[1:]:
        master_df = pd.merge(master_df, next_df, on='Month', how='outer')
        
    master_df['Month'] = pd.Categorical(master_df['Month'], categories=all_months, ordered=True)
        
    return master_df, source_cols

# Load data (Diagnostic variable removed)
master_df, source_cols = load_data()

if master_df.empty:
    st.error("No data loaded. Please ensure your CSV files are in the folder.")
    st.stop()

# --- MAIN CONTROLS ---
st.sidebar.header("1. Select Months")
active_months = st.sidebar.multiselect("Filter by Month:", all_months, default=[])
active_months.sort(key=lambda m: all_months.index(m))

st.sidebar.divider()
st.sidebar.header("2. Select Categories")
selected_cols = []

for name, cols in source_cols.items():
    selected = st.sidebar.multiselect(f"--- {name.upper()} ---", cols, default=[])
    selected_cols.extend(selected)

if not active_months or not selected_cols:
    st.info("👈 Please select at least one Month and one Category to view your data.")
    st.stop()

df = master_df[master_df['Month'].isin(active_months)].copy()
df = df.sort_values(by='Month')
view_df = df[['Month'] + selected_cols].copy()

# Live Graph
st.subheader("📈 Financial Trends")
graph_data = view_df.groupby('Month', observed=True)[selected_cols].sum()
st.line_chart(graph_data)

# Detailed Data Table
st.subheader("📊 Detailed Data")

cols_per_table = 6 
chunks = [selected_cols[i:i + cols_per_table] for i in range(0, len(selected_cols), cols_per_table)]

for chunk in chunks:
    current_cols = ['Month'] + chunk
    temp_df = view_df[current_cols].copy()
    
    totals = {"Month": "TOTAL"}
    for col in chunk:
        totals[col] = pd.to_numeric(temp_df[col], errors='coerce').sum()
        
    totals_df = pd.DataFrame([totals])
    final_chunk_df = pd.concat([temp_df, totals_df], ignore_index=True)
    
    st.dataframe(final_chunk_df, use_container_width=True, hide_index=True)
    st.write("") 
