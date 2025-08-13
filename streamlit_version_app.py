import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import requests
import numpy as np
import json

# --- Load Data (Cache to avoid reloading) ---
@st.cache_data
def load_stations(filename):
    return pd.read_csv(filename)

@st.cache_data
def precompute_distances(stations):
    num_stations = len(stations)
    distance_matrix = np.zeros((num_stations, num_stations))

    for i, station1 in stations.iterrows():
        for j, station2 in stations.iterrows():
            coords1 = (station1['Latitude'], station1['Longitude'])
            coords2 = (station2['Latitude'], station2['Longitude'])
            distance_matrix[i][j] = geodesic(coords1, coords2).km

    return distance_matrix

# --- Streamlit UI ---
st.title("🚇 Tube Meetup Planner")

# Input Mode Selection
input_mode = st.radio(
    "Input Mode:",
    ["Latitude/Longitude", "Station Dropdown"]
)

# Dynamic Input Fields
users = []
if input_mode == "Latitude/Longitude":
    st.header("Enter Coordinates")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("User 1 Latitude", key="lat1")
    with col2:
        lon = st.number_input("User 1 Longitude", key="lon1")
    users.append((lat, lon))

    # Add more users as needed...
else:
    stations = load_stations("tube_stations.csv")
    selected_station = st.selectbox(
        "User 1 Station",
        stations['Station'].tolist()
    )
    # Get coordinates from selected station
    station_data = stations[stations['Station'] == selected_station].iloc[0]
    users.append((station_data['Latitude'], station_data['Longitude']))

# --- Submit Button ---
if st.button("Find Best Station"):
    st.write("Calculating...")

    # Load data
    stations = load_stations("tube_stations.csv")
    distance_matrix = precompute_distances(stations)

    # Your logic here (simplified)
    midpoint = (
        sum(user[0] for user in users) / len(users),
        sum(user[1] for user in users) / len(users)
    )

    st.success(f"Midpoint: {midpoint}")
    # Add your TFL API calls here...

# --- Notes ---
st.markdown("""
- Replace `tube_stations.csv` with your file.
- Add error handling and more users as needed.
""")
