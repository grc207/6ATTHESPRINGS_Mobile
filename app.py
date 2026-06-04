import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
from datetime import datetime
import base64
import os

# 1. Page Configuration
st.set_page_config(page_title="LIVE LEADERBOARD", layout="wide")

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
    /* Keeps headers comfortably visible below the top monitor edge */
    .block-container {{
        padding-top: 3.2rem !important;
        padding-bottom: 0rem !important;
    }}
    
    /* Full-screen faint background logo */
    .stApp {{
        {bg_image_css}
        background-size: contain;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    
    /* Main titles formatting */
    h1 {{
        font-size: 30px !important;
        margin-top: 0px !important;
        margin-bottom: 20px !important;
        padding-top: 0px !important;
        text-align: center !important;
        font-weight: bold !important;
        color: #111111 !important;
    }}
    
    /* Standard table styles */
    table {{
        width: 100% !important;
        font-size: 24px !important;
        background-color: transparent !important;
        border-collapse: collapse !important;
        margin-left: auto;
        margin-right: auto;
    }}
    th {{
        background-color: transparent !important;
        color: #222222 !important;
        font-size: 26px !important;
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
    
    /* --- 20% SCALED DOWN DASHBOARD SKIN --- */
    .dashboard-scaled h3 {{
        font-size: 18px !important;
        font-weight: bold !important;
        color: #222222 !important;
        text-align: center !important;
        margin-top: 0px !important;
        margin-bottom: 8px !important;
    }}
    .dashboard-scaled table {{
        font-size: 19px !important;
        border: 2px solid #555555 !important;
    }}
    .dashboard-scaled th {{
        font-size: 21px !important;
        padding: 6px !important;
        border: 1px solid #555555 !important;
        border-bottom: 2px solid #555555 !important;
        background-color: rgba(0, 0, 0, 0.02) !important;
    }}
    .dashboard-scaled td {{
        padding: 6px !important;
        border: 1px solid #555555 !important;
    }}
    
    /* Hide background loading spinners for ultra-clean page transitions */
    div[data-testid="stStatusWidget"] {{
        display: none !important;
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
            roster = conn.read(worksheet="Runner Data", ttl="60s")
            roster.columns = roster.columns.str.strip()
            
            roster['Bib'] = pd.to_numeric(roster['Bib'], errors='coerce').fillna(0).astype(int)
            roster['Name'] = roster['First Name'].astype(str) + " " + roster['Last Name'].astype(str)
            
            reads = conn.read(worksheet="Data Input", ttl="60s")
            
            if reads.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            # Re-map incoming hardware columns: Col A -> Chip_ID, Col B -> Timestamp, Col C -> Bib
            reads.columns = ['Chip_ID', 'Timestamp', 'Bib']
            
            # Clean and isolate the raw text strings from any hardware apostrophe formatting
            reads['Timestamp'] = reads['Timestamp'].astype(str).str.strip("'\" ")
            reads['Bib'] = pd.to_numeric(reads['Bib'], errors='coerce').fillna(0).astype(int)

            start_time = datetime.strptime("08:00:00", "%H:%M:%S")
            
            # Aggregate based on your newly normalized column mappings
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
                time.sleep(2)
                continue
            else:
                st.error(f"Error processing live data: {e}")
                return pd.DataFrame(), pd.DataFrame()
                
    return pd.DataFrame(), pd.DataFrame()

# 3. Pull Data Metrics
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

# 4. Cycle & Speed Architecture
views = ["OVERALL 6-HOUR", "YOUTH DIVISION", "TOP RUNNERS DASHBOARD", "FEMALE 6-HOUR", "MALE 6-HOUR"]

if 'view_index' not in st.session_state:
    st.session_state.view_index = 0
if 'row_chunk' not in st.session_state:
    st.session_state.row_chunk = 0

current_view = views[st.session_state.view_index % len(views)]
ROWS_PER_SCREEN = 10 

if current_view == "YOUTH DIVISION":
    CURRENT_SCREEN_TIME = 10
elif current_view == "TOP RUNNERS DASHBOARD":
    CURRENT_SCREEN_TIME = 7
else:
    CURRENT_SCREEN_TIME = 5

# Master rendering placeholder
main_view_placeholder = st.empty()

if adult_data.empty and youth_data.empty:
    main_view_placeholder.info("Awaiting initial RFID reads...")
else:
    with main_view_placeholder.container():
        if current_view != "TOP RUNNERS DASHBOARD":
            # --- STANDARD LIST VIEW PATH ---
            st.markdown(f"<h1>🏆 {current_view}</h1>", unsafe_allow_html=True)
            
            cols_to_show = []
            display_df = pd.DataFrame()
            
            if current_view == "OVERALL 6-HOUR":
                display_df = adult_data.copy()
                cols_to_show
