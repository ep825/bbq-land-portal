import streamlit as st
import pandas as pd
import calendar
import os
import plotly.graph_objects as go

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
    errors = []

    for name, path in file_configs.items():
        if not os.path.exists(path):
            errors.append(f"Could not find {path}")
            continue
        
        try:
            df = pd.read_csv(path, encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            time_col = None
            for col in df.columns:
                if col.lower() in ['date', 'month']:
                    time_col = col
                    break
                    
            if not time_col:
                errors.append(f"{path} is missing a Date or Month column.")
                continue
            
            df = df.rename(columns={time_col: 'Month'})
            df['Month'] = df['Month'].astype(str).str.strip().str.title()
            
            df = df.dropna(subset=['Month'])
            df = df[df['Month'].isin(all_months)]
                
            cols = [c for c in df.columns if c != 'Month']
            source_cols[name] = sorted(cols)
            
            for col in cols:
                df[col] = df[col].apply(clean_currency)
                
            all_dfs.append(df)
            
        except Exception as e:
            errors.append(f"Error reading {path}: {e}")

    if not all_dfs:
        return pd.DataFrame(), {}, errors

    master_df = all_dfs[0]
    for next_df in all_dfs[1:]:
        master_df = pd.merge(master_df, next_df, on='Month', how='outer')
        
    master_df['Month'] = pd.Categorical(master_df['Month'], categories=all_months, ordered=True)
        
    return master_df, source_cols, errors

# Load data
master_df, source_cols, load_errors = load_data()

# --- SIDEBAR: MONTHS ONLY ---
st.sidebar.header("🗓️ Select Months")
st.sidebar.button("🔄 Refresh Data", on_click=st.cache_data.clear)
st.sidebar.divider()

if load_errors:
    for err in load_errors:
        st.error(err)

if master_df.empty:
    st.error("No data loaded. Please ensure your CSV files are in the folder and click 'Refresh Data'.")
    st.stop()

active_months = []
for month in all_months:
    if st.sidebar.checkbox(month, value=False):
        active_months.append(month)

if not active_months:
    st.info("👈 Please check at least one Month from the sidebar to view your data.")
    st.stop()

# Filter master data by selected months
df = master_df[master_df['Month'].isin(active_months)].copy()
df = df.sort_values(by='Month')

# --- CALCULATE TOTAL SALES FOR PERCENTAGES ---
ts_col = next((c for c in df.columns if str(c).strip().lower() == 'total sales'), None)
if ts_col:
    overall_total_sales = pd.to_numeric(df[ts_col], errors='coerce').sum()
else:
    overall_total_sales = 0

# --- TABS ---
tab1, tab2 = st.tabs(["🍽️ Category Breakdown", "💼 Financial Overview"])

# ==========================================
# TAB 1: CATEGORY DATA
# ==========================================
with tab1:
    st.header("Category Performance")
    cat_cols = source_cols.get("Category", [])
    
    selected_categories = st.multiselect("Select Categories to view:", cat_cols, default=[])
    
    if selected_categories:
        view_df_cat = df[['Month'] + selected_categories].copy()
        
        # Line Graph
        st.subheader("📈 Category Trends")
        graph_data_cat = view_df_cat.groupby('Month', observed=True)[selected_categories].sum()
        st.line_chart(graph_data_cat)

        # Table
        st.subheader("📊 Category Data")
        cols_per_table = 6 
        chunks = [selected_categories[i:i + cols_per_table] for i in range(0, len(selected_categories), cols_per_table)]

        for chunk in chunks:
            current_cols = ['Month'] + chunk
            temp_df = view_df_cat[current_cols].copy()
            
            totals = {"Month": "TOTAL"}
            pcts = {"Month": "% of Total Sales"}
            
            for col in chunk:
                col_total = pd.to_numeric(temp_df[col], errors='coerce').sum()
                totals[col] = col_total
                
                if overall_total_sales > 0:
                    pcts[col] = f"{(col_total / overall_total_sales) * 100:.2f}%"
                else:
                    pcts[col] = "N/A"
                
            totals_df = pd.DataFrame([totals, pcts])
            final_chunk_df = pd.concat([temp_df, totals_df], ignore_index=True)
            st.dataframe(final_chunk_df, use_container_width=True, hide_index=True)
            st.write("")
    else:
        st.info("Select categories from the dropdown above to view performance.")

# ==========================================
# TAB 2: FINANCIAL OVERVIEW
# ==========================================
with tab2:
    st.header("Sales, Expenses & Cash Flow")
    
    sales_cols = source_cols.get("Sales", [])
    exp_cols = source_cols.get("Expenses", [])
    cash_cols = source_cols.get("Cash", [])
    
    sales_card_col = [c for c in sales_cols if c.strip().lower() == 'card']
    sales_cash_col = [c for c in sales_cols if c.strip().lower() == 'cash']
    
    col1, col2 = st.columns(2)
    with col1:
        selected_expenses = st.multiselect("Select Expenses (Top Inner Bar):", exp_cols, default=[])
    with col2:
        selected_cash_sheet = st.multiselect("Select Cash Payouts (Bottom Inner Bar):", cash_cols, default=[])

    st.divider()

    # 1. DOUBLE-SIDED BAR GRAPH
    st.subheader("⚖️ Income vs. Outputs")
    
    agg_df = df.groupby('Month', observed=True).sum(numeric_only=True)
    
    if not agg_df.empty:
        val_sales_card = agg_df[sales_card_col].sum(axis=1) if sales_card_col else pd.Series([0]*len(agg_df), index=agg_df.index)
        val_expenses = agg_df[selected_expenses].sum(axis=1) if selected_expenses else pd.Series([0]*len(agg_df), index=agg_df.index)
        val_sales_cash = agg_df[sales_cash_col].sum(axis=1) if sales_cash_col else pd.Series([0]*len(agg_df), index=agg_df.index)
        val_cash_sheet = agg_df[selected_cash_sheet].sum(axis=1) if selected_cash_sheet else pd.Series([0]*len(agg_df), index=agg_df.index)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=agg_df.index, y=val_sales_card,
            name='Income: Card (Sales)',
            marker_color='#2ca02c', 
            width=0.5
        ))

        fig.add_trace(go.Bar(
            x=agg_df.index, y=val_expenses,
            name='Output: Selected Expenses',
            marker_color='#d62728', 
            width=0.25
        ))

        fig.add_trace(go.Bar(
            x=agg_df.index, y=-val_sales_cash,
            customdata=val_sales_cash, 
            hovertemplate="%{x}<br>Income: Cash (Sales): $%{customdata:,.2f}<extra></extra>",
            name='Income: Cash (Sales)',
            marker_color='#1f77b4', 
            width=0.5
        ))

        fig.add_trace(go.Bar(
            x=agg_df.index, y=-val_cash_sheet,
            customdata=val_cash_sheet,
            hovertemplate="%{x}<br>Output: Selected Cash: $%{customdata:,.2f}<extra></extra>",
            name='Output: Selected Cash',
            marker_color='#ff7f0e', 
            width=0.25
        ))

        fig.update_layout(
            barmode='overlay',
            yaxis_title="Amount ($)",
            yaxis_tickformat="$,.0f", 
            hovermode="x unified",
            margin=dict(t=30, b=0, l=0, r=0)
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # 2. DETAILED DATA TABLES (NOW SPLIT INTO SUB-TABS)
    st.subheader("📊 Financial Data Tables")
    
    sub_tab_exp, sub_tab_cash = st.tabs(["💳 Card & Expenses", "💵 Cash Flow"])
    
    # --- SUB TAB: EXPENSES ---
    with sub_tab_exp:
        exp_table_cols = sales_card_col + selected_expenses
        
        if exp_table_cols:
            view_df_exp = df[['Month'] + exp_table_cols].copy()
            cols_per_table = 6 
            chunks = [exp_table_cols[i:i + cols_per_table] for i in range(0, len(exp_table_cols), cols_per_table)]

            for chunk in chunks:
                current_cols = ['Month'] + chunk
                temp_df = view_df_exp[current_cols].copy()
                
                totals = {"Month": "TOTAL"}
                pcts = {"Month": "% of Total Sales"}
                
                for col in chunk:
                    col_total = pd.to_numeric(temp_df[col], errors='coerce').sum()
                    totals[col] = col_total
                    
                    if overall_total_sales > 0:
                        pcts[col] = f"{(col_total / overall_total_sales) * 100:.2f}%"
                    else:
                        pcts[col] = "N/A"
                    
                totals_df = pd.DataFrame([totals, pcts])
                final_chunk_df = pd.concat([temp_df, totals_df], ignore_index=True)
                st.dataframe(final_chunk_df, use_container_width=True, hide_index=True)
                st.write("")
        else:
            st.info("Select expenses above to generate the Card & Expenses table.")

    # --- SUB TAB: CASH ---
    with sub_tab_cash:
        cash_table_cols = sales_cash_col + selected_cash_sheet
        
        if cash_table_cols:
            view_df_cash = df[['Month'] + cash_table_cols].copy()
            cols_per_table = 6 
            chunks = [cash_table_cols[i:i + cols_per_table] for i in range(0, len(cash_table_cols), cols_per_table)]

            for chunk in chunks:
                current_cols = ['Month'] + chunk
                temp_df = view_df_cash[current_cols].copy()
                
                totals = {"Month": "TOTAL"}
                pcts = {"Month": "% of Total Sales"}
                
                for col in chunk:
                    col_total = pd.to_numeric(temp_df[col], errors='coerce').sum()
                    totals[col] = col_total
                    
                    if overall_total_sales > 0:
                        pcts[col] = f"{(col_total / overall_total_sales) * 100:.2f}%"
                    else:
                        pcts[col] = "N/A"
                    
                totals_df = pd.DataFrame([totals, pcts])
                final_chunk_df = pd.concat([temp_df, totals_df], ignore_index=True)
                st.dataframe(final_chunk_df, use_container_width=True, hide_index=True)
                st.write("")
        else:
            st.info("Select cash payouts above to generate the Cash Flow table.")
