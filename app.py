import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from datetime import datetime

# 1. Page Configuration
st.set_page_config(page_title="LIVE LEADERBOARD", layout="wide")

# Native raw GitHub hosting link to prevent browser hotlink blocking
LOGO_URL = "https://raw.githubusercontent.com/streamlit/tarbell/master/tests/data/logo.png" 

st.markdown(
    f"""
    <style>
    /* Tighten top margins to push tables as high up the monitor as possible */
    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
    }}
    
    /* Full-screen faint background logo */
    .stApp {{
        background-image: linear-gradient(rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.94)), url("{LOGO_URL}");
        background-size: contain;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    
    /* Shrunk, centered title layout */
    h1 {{
        font-size: 42px !important;
        margin-top: 0px !important;
        margin-bottom: 15px !important;
        padding-top: 0px !important;
        text-align: center !important;
    }}
    
    /* Center-aligned, minimalist, border-free table design */
    table {{
        width: 100% !important;
        font-size: 26px !important;
        background-color: transparent !important;
        border-collapse: collapse !important;
        margin-left: auto;
        margin-right: auto;
    }}
    th {{
        background-color: transparent !important;
        color: #222222 !important;
        font-size: 28px !important;
        font-weight: bold !important;
        text-align: center !important;
        padding: 10px !important;
        border-bottom: 2px solid #444444 !important;
    }}
    td {{
        padding: 12px !important;
        font-weight: 500 !important;
        text-align: center !important;
        border-bottom: 1px solid #e0e0e0 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# 2. Data Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def get_processed_data():
    try:
        # Load Roster from "Runner Data"
        roster = conn.read(worksheet="Runner Data", ttl="0s")
        roster.columns = roster.columns.str.strip()
        
        # Clean roster columns and compile Name
        roster['Bib'] = pd.to_numeric(roster['Bib'], errors='coerce').fillna(0).astype(int)
        roster['Name'] = roster['First Name'].astype(str) + " " + roster['Last Name'].astype(str)
        
        # Load Raw Reads from "Data Input"
        reads = conn.read(worksheet="Data Input", ttl="0s")
        reads.columns = reads.columns.str.strip()
        reads['Bib'] = pd.to_numeric(reads['Bib'], errors='coerce').fillna(0).astype(int)
        
        if reads.empty or 'Bib' not in reads.columns:
            return pd.DataFrame(), pd.DataFrame()

        # Race configuration
        start_time = datetime.strptime("08:00:00", "%H:%M:%S")
        
        # Calculate loops (count of raw reads) and latest read time per bib
        stats = reads.groupby('Bib').agg(
            Loop_Count=('Timestamp', 'count'),
            Last_Read=('Timestamp', 'max')
        ).reset_index()
        
        # Merge raw metrics with runner details
        df = pd.merge(roster, stats, on='Bib', how='inner')
        
        # Calculate Mileage (1 read = 1 loop = 4 miles)
        df['Mileage'] = df['Loop_Count'] * 4
        
        # Calculate Elapsed Time string from 8:00 AM
        def calc_elapsed(ts_str):
            try:
                ts = datetime.strptime(str(ts_str).split()[-1], "%H:%M:%S")
                delta = ts - start_time
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except:
                return "00:00:00"
                
        df['Overall Time'] = df['Last_Read'].apply(calc_elapsed)
        
        # FIXED: Look for ANY distance row containing the word "Youth" case-insensitively
        df['distance'] = df['distance'].astype(str).str.strip()
        youth_mask = df['distance'].str.contains("Youth", case=False, na=False)
        
        adult_df = df[~youth_mask & df['distance'].str.contains("6HR", case=False, na=False)].copy()
        youth_df = df[youth_mask].copy()
        
        # Strict Sorting: Loops (Highest) -> Last Read Timestamp (Earliest)
        adult_df = adult_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
        youth_df = youth_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
        
        return adult_df, youth_df
    except Exception as e:
        st.error(f"Error processing live data: {e}")
        return pd.DataFrame(), pd.DataFrame()

# 3. Process Live Metrics and Assign Rankings
adult_data, youth_data = get_processed_data()

if not adult_data.empty:
    # Generate overall numeric positions for adults (Starting strictly at 1)
    adult_data['Position'] = [i+1 for i in range(len(adult_data))]
    
    # Generate Class Places for adults only (Starting strictly at 1)
    adult_data['Class Place'] = ""
    m_count, f_count = 1, 1
    for idx, row in adult_data.iterrows():
        if str(row['gender']).upper().strip() == 'M':
            adult_data.at[idx, 'Class Place'] = f"M{m_count}"
            m_count += 1
        elif str(row['gender']).upper().strip() == 'F':
            adult_data.at[idx, 'Class Place'] = f"F{f_count}"
            f_count += 1

if not youth_data.empty:
    # Generate division ranking explicitly for the youth pool (Starting strictly at 1)
    youth_data['Class Place'] = [f"Y{i+1}" for i in range(len(youth_data))]

# 4. Cycle & Chunk State Setup
views = ["OVERALL 6-HOUR", "FEMALE 6-HOUR", "MALE 6-HOUR", "TOP 5 DASHBOARD", "YOUTH DIVISION"]

if 'view_index' not in st.session_state:
    st.session_state.view_index = 0
if 'row_chunk' not in st.session_state:
    st.session_state.row_chunk = 0

current_view = views[st.session_state.view_index % len(views)]
ROWS_PER_SCREEN = 10 

# 5. Render Layout Title
st.markdown(f"<h1>🏆 {current_view}</h1>", unsafe_allow_html=True)

if adult_data.empty and youth_data.empty:
    st.info("Awaiting initial RFID reads...")
else:
    cols_to_show = []
    display_df = pd.DataFrame()
    is_dashboard = False
    
    if current_view == "OVERALL 6-HOUR":
        display_df = adult_data.copy()
        cols_to_show = ['Position', 'Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        
    elif current_view == "FEMALE 6-HOUR":
        display_df = adult_data[adult_data['gender'].str.upper().str.strip() == 'F'].copy()
        cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        
    elif current_view == "MALE 6-HOUR":
        display_df = adult_data[adult_data['gender'].str.upper().str.strip() == 'M'].copy()
        cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        
    elif current_view == "YOUTH DIVISION":
        display_df = youth_data.copy()
        cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        
    elif current_view == "TOP 5 DASHBOARD":
        is_dashboard = True
        col1, col2 = st.columns(2)
        podium_cols = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        
        with col1:
            st.markdown("<h3 style='text-align: center; margin-top:0px;'>🏃‍♂️ Top 5 Men</h3>", unsafe_allow_html=True)
            top_m = adult_data[adult_data['gender'].str.upper().str.strip() == 'M'].head(5).copy()
            if not top_m.empty:
                st.table(top_m[podium_cols].rename(columns={'Loop_Count': 'Loops'}), hide_index=True)
            else:
                st.write("No entries yet")
            
        with col2:
            st.markdown("<h3 style='text-align: center; margin-top:0px;'>🏃‍♀️ Top 5 Women</h3>", unsafe_allow_html=True)
            top_f = adult_data[adult_data['gender'].str.upper().str.strip() == 'F'].head(5).copy()
            if not top_f.empty:
                st.table(top_f[podium_cols].rename(columns={'Loop_Count': 'Loops'}), hide_index=True)
            else:
                st.write("No entries yet")

    # FIXED scrolling/chunking architecture for long lists
    if not is_dashboard:
        total_rows = len(display_df)
        
        if total_rows > 0:
            start_row = st.session_state.row_chunk * ROWS_PER_SCREEN
            end_row = start_row + ROWS_PER_SCREEN
            
            sliced_df = display_df.iloc[start_row:end_row]
            st.table(sliced_df[cols_to_show].rename(columns={'Loop_Count': 'Loops'}), hide_index=True)
            
            # If we reached the end of this category's list, advance the page index
            if end_row >= total_rows:
                st.session_state.row_chunk = 0
                st.session_state.view_index += 1
            else:
                st.session_state.row_chunk += 1
        else:
            # If an active screen list is entirely empty, skip to the next view instantly
            st.session_state.row_chunk = 0
            st.session_state.view_index += 1
    else:
        # Dashboard screen doesn't chunk, move directly to next view on the next cycle tick
        st.session_state.row_chunk = 0
        st.session_state.view_index += 1

# 6. Refresh interval (12 seconds)
time.sleep(12)
st.rerun()
