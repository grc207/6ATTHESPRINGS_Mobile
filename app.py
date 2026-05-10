import streamlit as st
from streamlit_gsheets import GSheetsConnection # Try this first
# If that fails, try: from st_gsheets_connection import GSheetsConnection
import time

# Set to wide mode for the big screen
st.set_page_config(layout="wide")

# Connect using your private credentials
# (Streamlit will look for your JSON data in secrets.toml)
conn = st.connection("gsheets", type=GSheetsConnection)

# Function to pull the specific tab
def get_leaderboard():
    # ttl="5s" means it checks the Google Sheet for updates every 5 seconds
    return conn.read(worksheet="Statistics", ttl="5s")

# --- ROTATION LOGIC ---
if 'view_index' not in st.session_state:
    st.session_state.view_index = 0

views = ["Overall 6-Hour", "Female 6-Hour", "Male 6-Hour", "Youth Event"]
current_view = views[st.session_state.view_index % len(views)]

# Display Title
st.markdown(f"# 🏆 {current_view}")

# Get Data
data = get_leaderboard()

# Filter based on your sheet columns
if current_view == "Overall 6-Hour":
    df_display = data[data['distance'] == '6HR']
elif current_view == "Female 6-Hour":
    df_display = data[(data['distance'] == '6HR') & (data['gender'] == 'F')]
elif current_view == "Male 6-Hour":
    df_display = data[(data['distance'] == '6HR') & (data['gender'] == 'M')]
else:
    # Captures anything with "Youth" in the distance name
    df_display = data[data['distance'].str.contains("Youth", na=False)]

# Sort by Laps (Primary) and Fastest Lap (Secondary Tie-breaker)
# Note: Ensure these column names match your sheet exactly
df_sorted = df_display.sort_values(by=['Laps', 'Fastest Lap'], ascending=[False, True]).head(15)

# Show the table with specific columns
st.table(df_sorted[['Bib', 'First Name', 'Last Name', 'Laps', 'Fastest Lap']])

# Auto-refresh and rotate every 20 seconds
time.sleep(20)
st.session_state.view_index += 1
st.rerun()
