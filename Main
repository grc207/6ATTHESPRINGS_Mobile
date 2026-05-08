import streamlit as st
import pandas as pd
import time
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration for TV
st.set_page_config(page_title="Race Leaderboard", layout="wide")

# Custom CSS to make text BIG for TV screens
st.markdown("""
    <style>
    .big-font { font-size:50px !important; font-weight: bold; }
    .medium-font { font-size:30px !important; }
    thead tr th { font-size: 25px !important; }
    tbody tr td { font-size: 25px !important; }
    </style>
    """, unsafe_allow_name_to_id=True)

# 2. Connect to your Google Sheet
# We use the GSheetsConnection which is very fast for reading
conn = st.connection("gsheets", type=GSheetsConnection)

def get_stats():
    # Replace 'Statistics' with the exact name of your stats tab
    df = conn.read(worksheet="Statistics", ttl="5s") 
    return df

# 3. Rotation Logic (Overall -> Female -> Male -> Youth)
if 'rotation' not in st.session_state:
    st.session_state.rotation = 0

categories = ["Overall 6-Hour", "Female 6-Hour", "Male 6-Hour", "Youth Event"]
current_view = categories[st.session_state.rotation % len(categories)]

# Header
st.markdown(f'<p class="big-font">🏆 {current_view}</p>', unsafe_allow_html=True)

# 4. Filter and Display
df = get_stats()

if current_view == "Overall 6-Hour":
    display_df = df[df['distance'] == '6HR'].sort_values(by='Laps', ascending=False).head(10)
elif current_view == "Female 6-Hour":
    display_df = df[(df['distance'] == '6HR') & (df['gender'] == 'F')].sort_values(by='Laps', ascending=False).head(10)
elif current_view == "Male 6-Hour":
    display_df = df[(df['distance'] == '6HR') & (df['gender'] == 'M')].sort_values(by='Laps', ascending=False).head(10)
else: # Youth
    display_df = df[df['distance'].str.contains('Youth')].sort_values(by='Laps', ascending=False)

# Display the table
st.table(display_df[['Bib', 'First Name', 'Last Name', 'Laps', 'Fastest Lap']])

# 5. Auto-Refresh & Rotate (20 seconds per screen)
time.sleep(20)
st.session_state.rotation += 1
st.rerun()
