import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from datetime import datetime

# 1. Page Configuration & Full-Screen Background CSS
st.set_page_config(page_title="LIVE LEADERBOARD", layout="wide")

st.markdown(
    """
    <style>
    /* Faint full-screen background logo */
    .stApp {
        background-image: linear-gradient(rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.92)), url("app/static/logo.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    
    /* Monitor-friendly table styling */
    table {
        width: 100% !important;
        font-size: 24px !important;
    }
    th {
        background-color: #1f77b4 !important;
        color: white !important;
        font-size: 26px !important;
        font-weight: bold !important;
    }
    td {
        padding: 12px !important;
        font-weight: 500 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 2. Data Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def get_raw_data():
    """
    Assumes a 'Roster' sheet with: Bib, Name, Gender, Age, Event
    And a 'Sheet 1' sheet where RFID logs hit: Bib, Timestamp
    Adjust worksheet names below if your script writes elsewhere.
    """
    try:
        # Load Roster
        roster = conn.read(worksheet="Roster", ttl="0s")
        roster.columns = roster.columns.str.strip()
        roster['Bib'] = pd.to_numeric(roster['Bib'], errors='coerce').fillna(0).astype(int)
        
        # Load Raw Reads (Assuming 'Sheet 1' or your log sheet)
        reads = conn.read(worksheet="Sheet 1", ttl="0s")
        reads.columns = reads.columns.str.strip()
        reads['Bib'] = pd.to_numeric(reads['Bib'], errors='coerce').fillna(0).astype(int)
        
        if reads.empty or 'Bib' not in reads.columns:
            return pd.DataFrame()

        # Group reads to find Loop Count and Max (latest) Timestamp
        # Assuming Event starts at 8:00 AM. Adjust date if needed.
        start_time = datetime.strptime("08:00:00", "%H:%M:%S")
        
        # Calculate loops and last read time per bib
        stats = reads.groupby('Bib').agg(
            Loop_Count=('Timestamp', 'count'),
            Last_Read=('Timestamp', 'max')
        ).reset_index()
        
        # Merge with roster info
        df = pd.merge(roster, stats, on='Bib', how='inner')
        
        # Filter for 6HR event
        df = df[df['Event'].str.contains("6HR", na=False, case=False)].copy()
        
        # Calculate Mileage (e.g., 4 miles per loop)
        df['Mileage'] = df['Loop_Count'] * 4
        
        # Calculate Elapsed Time string from 8:00 AM
        def calc_elapsed(ts_str):
            try:
                # Adjust format matching your Python RFID writer string format
                ts = datetime.strptime(str(ts_str).split()[-1], "%H:%M:%S")
                delta = ts - start_time
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except:
                return "00:00:00"
                
        df['Overall Time'] = df['Last_Read'].apply(calc_elapsed)
        
        # Strict Sorting: Loops (Highest) -> Last Read Timestamp (Earliest/Shortest Time)
        df = df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
        
        return df
    except Exception as e:
        st.error(f"Error processing live data: {e}")
        return pd.DataFrame()

# 3. Process Live Metrics and Positions
data = get_raw_data()

if not data.empty:
    # Generate overall positions (O1, O2...)
    data['Overall_Pos'] = [f"O{i+1}" for i in range(len(data))]
    
    # Generate Gender positions (M1, M2... / F1, F2...)
    data['Gender_Pos'] = ""
    m_count, f_count = 1, 1
    for idx, row in data.iterrows():
        if row['Gender'] == 'M':
            data.at[idx, 'Gender_Pos'] = f"M{m_count}"
            m_count += 1
        elif row['Gender'] == 'F':
            data.at[idx, 'Gender_Pos'] = f"F{f_count}"
            f_count += 1

# 4. Cycle & Chunk State Setup
# Pages to cycle through
views = ["OVERALL 6-HOUR", "FEMALE 6-HOUR", "MALE 6-HOUR", "PODIUM & YOUTH"]

if 'view_index' not in st.session_state:
    st.session_state.view_index = 0
if 'row_chunk' not in st.session_state:
    st.session_state.row_chunk = 0

current_view = views[st.session_state.view_index % len(views)]
ROWS_PER_SCREEN = 12  # Comfortably fits a standard 1080p monitor without scrolling layout

# 5. Render Logic based on view
st.markdown(f"<h1 style='text-align: center; font-size: 55px; margin-bottom: 20px;'>🏆 {current_view}</h1>", unsafe_allow_html=True)

if data.empty:
    st.info("Awaiting initial RFID reads...")
else:
    if current_view == "OVERALL 6-HOUR":
        display_df = data.copy()
        display_df['Position'] = display_df['Overall_Pos']
        
    elif current_view == "FEMALE 6-HOUR":
        display_df = data[data['Gender'] == 'F'].copy()
        display_df['Position'] = display_df['Gender_Pos']
        
    elif current_view == "MALE 6-HOUR":
        display_df = data[data['Gender'] == 'M'].copy()
        display_df['Position'] = display_df['Gender_Pos']
        
    elif current_view == "PODIUM & YOUTH":
        # Custom Dashboard Layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏃‍♂️ Top 5 Men")
            top_m = data[data['Gender'] == 'M'].head(5).copy()
            top_m['Position'] = top_m['Gender_Pos']
            st.table(top_m[['Position', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']].rename(columns={'Loop_Count': 'Loops'}))
            
        with col2:
            st.markdown("### 🏃‍♀️ Top 5 Women")
            top_f = data[data['Gender'] == 'F'].head(5).copy()
            top_f['Position'] = top_f['Gender_Pos']
            st.table(top_f[['Position', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']].rename(columns={'Loop_Count': 'Loops'}))
            
        st.markdown("---")
        st.markdown("### 🧒 All Youth (Under 18)")
        # Assuming age column exists on Roster. Adjust cutoff age if necessary.
        youth_df = data[data['Age'] < 18].copy()
        youth_df['Position'] = youth_df['Overall_Pos']
        st.table(youth_df[['Position', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']].rename(columns={'Loop_Count': 'Loops'}))
        
        display_df = pd.DataFrame() # Block normal chunk processing for dashboard page

    # Handle Paging/Vertical Chunking for long lists
    if not display_df.empty:
        total_rows = len(display_df)
        start_row = st.session_state.row_chunk * ROWS_PER_SCREEN
        end_row = start_row + ROWS_PER_SCREEN
        
        # Display slice
        sliced_df = display_df.iloc[start_row:end_row]
        st.table(sliced_df[['Position', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']].rename(columns={'Loop_Count': 'Loops'}))
        
        # Advance chunks or switch pages
        if end_row >= total_rows:
            st.session_state.row_chunk = 0
            st.session_state.view_index += 1
        else:
            st.session_state.row_chunk += 1
    else:
        # If dashboard view, just advance to next category on next tick
        st.session_state.row_chunk = 0
        st.session_state.view_index += 1

# 6. Screen Rotation Interval (e.g., 12 seconds per view/chunk)
time.sleep(12)
st.rerun()
