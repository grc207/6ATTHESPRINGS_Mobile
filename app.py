import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from datetime import datetime
import base64
import os

# 1. Page Configuration
st.set_page_config(page_title="FINAL RACER LOOKUP", layout="wide")

# --- SECURE BACKGROUND LOGO ENGINE ---
bg_image_css = ""
image_exts = ["logo.png", "logo.jpg", "logo.jpeg"]
found_image = None

for ext in image_exts:
    if os.path.exists(ext):
        found_image = ext
        break

if found_image:
    try:
        with open(found_image, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
            bg_image_css = f"background-image: linear-gradient(rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.94)), url(data:image/png;base64,{encoded_string});"
    except Exception:
        bg_image_css = "background-color: #f9f9f9;"
else:
    bg_image_css = "background-color: #f9f9f9;"

st.markdown(
    f"""
    <style>
    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }}
    
    .stApp {{
        {bg_image_css}
        background-size: contain;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    
    h1 {{
        font-size: 30px !important;
        margin-top: 0px !important;
        margin-bottom: 5px !important;
        text-align: center !important;
        font-weight: bold !important;
        color: #111111 !important;
    }}

    .byline {{
        font-size: 16px !important;
        text-align: center !important;
        font-style: italic !important;
        color: #555555 !important;
        margin-bottom: 25px !important;
    }}
    
    table {{
        width: 100% !important;
        font-size: 22px !important;
        background-color: transparent !important;
        border-collapse: collapse !important;
    }}
    th {{
        background-color: transparent !important;
        color: #222222 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        text-align: center !important;
        padding: 8px !important;
        border-bottom: 2px solid #444444 !important;
    }}
    td {{
        padding: 8px !important;
        font-weight: 500 !important;
        text-align: center !important;
        border-bottom: 1px solid #e0e0e0 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# 2. Hardlocked Data Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def get_frozen_data():
    try:
        # Load final fixed datasets with a frozen high TTL to prevent constant data refetches
        roster = conn.read(worksheet="Runner Data", ttl="30d")
        roster.columns = roster.columns.str.strip()
        
        roster['Bib'] = pd.to_numeric(roster['Bib'], errors='coerce').fillna(0).astype(int)
        roster['Name'] = roster['First Name'].astype(str) + " " + roster['Last Name'].astype(str)
        
        reads = conn.read(worksheet="Data Input", ttl="30d")
        
        if reads.empty:
            return pd.DataFrame(), pd.DataFrame()
        
        reads = reads.iloc[:, :3]
        reads.columns = ['Chip_ID', 'Timestamp', 'Bib']
        
        reads['Bib'] = pd.to_numeric(reads['Bib'], errors='coerce').fillna(0).astype(int)
        reads = reads[reads['Bib'] > 0]

        if len(reads) == 0:
            return pd.DataFrame(), pd.DataFrame()

        # Configured historic event start date: June 20th at 8:00 AM
        start_time = datetime.strptime("2026-06-20 08:00:00", "%Y-%m-%d %H:%M:%S")
        
        def parse_to_time_object(ts_val):
            try:
                ts_str = str(ts_val).strip("'\" ").split()[-1]
                # Combine static date prefix with individual runner timestamps
                return datetime.strptime(f"2026-06-20 {ts_str}", "%Y-%m-%d %H:%M:%S")
            except Exception:
                return start_time

        reads['Time_Obj'] = reads['Timestamp'].apply(parse_to_time_object)
        
        stats = reads.groupby('Bib').agg(
            Loop_Count=('Time_Obj', 'count'),
            Max_Time_Obj=('Time_Obj', 'max')
        ).reset_index()
        
        df = pd.merge(roster, stats, on='Bib', how='inner')
        df['Mileage'] = df['Loop_Count'] * 4
        
        def calc_elapsed(max_time):
            try:
                delta = max_time - start_time
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except Exception:
                return "00:00:00"
                
        df['Overall Time'] = df['Max_Time_Obj'].apply(calc_elapsed)
        df['Last_Read'] = df['Max_Time_Obj'].dt.strftime('%H:%M:%S')
        
        df['distance'] = df['distance'].astype(str).str.strip()
        youth_mask = df['distance'].str.contains("Youth", case=False, na=False)
        
        adult_df = df[~youth_mask & df['distance'].str.contains("6HR", case=False, na=False)].copy()
        youth_df = df[youth_mask].copy()
        
        adult_df = adult_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
        youth_df = youth_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
        
        return adult_df, youth_df
    except Exception as e:
        st.error(f"Error loading final event archive dataset: {e}")
        return pd.DataFrame(), pd.DataFrame()

# 3. Pull Data Snapshots
adult_data, youth_data = get_frozen_data()

if not adult_data.empty:
    adult_data['Position'] = [i+1 for i in range(len(adult_data))]
    adult_data['Class Place'] = ""
    m_count, f_count, x_count = 1, 1, 1
    for idx, row in adult_data.iterrows():
        gen_val = str(row['gender']).upper().strip()
        if gen_val == 'M':
            adult_data.at[idx, 'Class Place'] = f"M{m_count}"
            m_count += 1
        elif gen_val == 'F':
            adult_data.at[idx, 'Class Place'] = f"F{f_count}"
            f_count += 1
        elif gen_val == 'X':
            adult_data.at[idx, 'Class Place'] = f"X{x_count}"
            x_count += 1

if not youth_data.empty:
    youth_data['Class Place'] = [f"Y{i+1}" for i in range(len(youth_data))]

# 4. Interactive Search UI Components with Required Byline
st.markdown("<h1>🔍 COMPETITOR RESULTS LOOKUP</h1>", unsafe_allow_html=True)
st.markdown('<div class="byline">results are not official until recorded on UltraSignup</div>', unsafe_allow_html=True)

search_query = st.text_input("Search by Name or Bib Number:", value="", placeholder="e.g. Bob or 142").strip()

category = st.radio(
    "Filter Division:",
    options=["Overall (Adults)", "Male", "Female", "Non-Binary", "Youth"],
    horizontal=True
)

# 5. Core Filtering Logic
if adult_data.empty and youth_data.empty:
    st.info("No verified historical event logs found.")
else:
    if category == "Youth":
        display_df = youth_data.copy()
        cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
    else:
        if category == "Overall (Adults)":
            display_df = adult_data.copy()
            cols_to_show = ['Position', 'Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        elif category == "Male":
            display_df = adult_data[adult_data['gender'].str.upper().str.strip() == 'M'].copy()
            cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        elif category == "Female":
            display_df = adult_data[adult_data['gender'].str.upper().str.strip() == 'F'].copy()
            cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
        elif category == "Non-Binary":
            display_df = adult_data[adult_data['gender'].str.upper().str.strip() == 'X'].copy()
            cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']

    if search_query:
        name_match = display_df['Name'].str.contains(search_query, case=False, na=False)
        bib_match = display_df['Bib'].astype(str).str.contains(search_query, na=False)
        display_df = display_df[name_match | bib_match]

    if not display_df.empty:
        st.table(display_df[cols_to_show].rename(columns={'Loop_Count': 'Loops'}), hide_index=True)
    else:
        st.warning("No runners found matching your selection criteria.")
