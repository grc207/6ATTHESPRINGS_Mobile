import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from datetime import datetime
import base64
import os

# 1. Page Configuration
st.set_page_config(page_title="RACER LOOKUP", layout="wide")

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
        margin-bottom: 20px !important;
        text-align: center !important;
        font-weight: bold !important;
        color: #111111 !important;
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

# 2. Data Connection
conn = st.connection("gsheets", type=GSheetsConnection)

def get_processed_data():
    for attempt in range(3):
        try:
            # Load Roster
            roster = conn.read(worksheet="Runner Data", ttl="10s")  # Lower TTL for interactive lookup snappiness
            roster.columns = roster.columns.str.strip()
            
            roster['Bib'] = pd.to_numeric(roster['Bib'], errors='coerce').fillna(0).astype(int)
            roster['Name'] = roster['First Name'].astype(str) + " " + roster['Last Name'].astype(str)
            
            # Load Data Input Sheet
            reads = conn.read(worksheet="Data Input", ttl="10s")
            
            if reads.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            reads = reads.iloc[:, :3]
            reads.columns = ['Chip_ID', 'Timestamp', 'Bib']
            
            if pd.api.types.is_datetime64_any_dtype(reads['Timestamp']):
                reads['Timestamp'] = reads['Timestamp'].dt.strftime('%H:%M:%S')
            else:
                reads['Timestamp'] = reads['Timestamp'].astype(str).str.strip("'\" ")
            
            reads['Bib'] = pd.to_numeric(reads['Bib'], errors='coerce').fillna(0).astype(int)
            reads = reads[reads['Bib'] > 0]

            if len(reads) == 0:
                return pd.DataFrame(), pd.DataFrame()

            start_time = datetime.strptime("08:00:00", "%H:%M:%S")
            
            stats = reads.groupby('Bib').agg(
                Loop_Count=('Timestamp', 'count'),
                Last_Read=('Timestamp', 'max')
            ).reset_index()
            
            df = pd.merge(roster, stats, on='Bib', how='inner')
            df['Mileage'] = df['Loop_Count'] * 4
            
            def calc_elapsed(ts_str):
                try:
                    clean_ts = str(ts_str).strip("'\" ")
                    ts_part = clean_ts.split()[-1]
                    
                    ts = datetime.strptime(ts_part, "%H:%M:%S")
                    delta = ts - start_time
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                except Exception:
                    return "00:00:00"
                    
            df['Overall Time'] = df['Last_Read'].apply(calc_elapsed)
            
            df['distance'] = df['distance'].astype(str).str.strip()
            youth_mask = df['distance'].str.contains("Youth", case=False, na=False)
            
            adult_df = df[~youth_mask & df['distance'].str.contains("6HR", case=False, na=False)].copy()
            youth_df = df[youth_mask].copy()
            
            adult_df = adult_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
            youth_df = youth_df.sort_values(by=['Loop_Count', 'Last_Read'], ascending=[False, True]).reset_index(drop=True)
            
            return adult_df, youth_df

        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                time.sleep(1)
                continue
            else:
                st.error(f"Error processing live data: {e}")
                return pd.DataFrame(), pd.DataFrame()
                
    return pd.DataFrame(), pd.DataFrame()

# 3. Pull and Master-Rank Data
adult_data, youth_data = get_processed_data()

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

# 4. Interactive Search UI Components
st.markdown("<h1>🔍 COMPETITOR RESULTS LOOKUP</h1>", unsafe_allow_html=True)

# UI Inputs side-by-side or stacked cleanly
search_query = st.text_input("Search by Name or Bib Number:", value="", placeholder="e.g. Bob or 142").strip()

category = st.radio(
    "Filter Division:",
    options=["Overall (Adults)", "Male", "Female", "Non-Binary", "Youth"],
    horizontal=True
)

# 5. Core Filtering Logic
if adult_data.empty and youth_data.empty:
    st.info("Awaiting initial RFID reads...")
else:
    # Segment data based on selected category radio button
    if category == "Youth":
        display_df = youth_data.copy()
        cols_to_show = ['Class Place', 'Bib', 'Name', 'Loop_Count', 'Mileage', 'Overall Time']
    else:
        # Base filter handles excluding youth out of overall paths
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

    # Apply text filter if query exists
    if search_query:
        # Check both name match and partial/exact bib conversions
        name_match = display_df['Name'].str.contains(search_query, case=False, na=False)
        bib_match = display_df['Bib'].astype(str).str.contains(search_query, na=False)
        display_df = display_df[name_match | bib_match]

    # Render results
    if not display_df.empty:
        st.table(display_df[cols_to_show].rename(columns={'Loop_Count': 'Loops'}), hide_index=True)
    else:
        st.warning("No runners found matching your selection criteria.")
