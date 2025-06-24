import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import requests
import numpy as np
import time

# --- Cached Data Loading ---
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

# --- TFL API Functions ---
def get_travel_time(start_station_id, end_station_id, api_key, retries=3):
    if start_station_id == end_station_id:
        return None
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {"app_key": api_key, "mode": "tube"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'journeys' not in data or not data['journeys']:
            return None
            
        return data['journeys'][0]['duration']
    except requests.exceptions.HTTPError as e:
        if response.status_code == 500 and retries > 0:
            time.sleep(1)
            return get_travel_time(start_station_id, end_station_id, api_key, retries - 1)
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

# --- Streamlit UI ---
st.title("🚇 Tube Meetup Planner")

# Input Mode Selection
input_mode = st.radio(
    "Input Mode:",
    ["Station Dropdown", "Coordinates"],
    index=0,
    horizontal=True
)

# Initialize users list
users = []
stations_data = load_stations("tube_stations.csv")

if input_mode == "Station Dropdown":
    st.header("Select Stations for All Travelers")
    
    # Required travelers (first 2)
    st.markdown("### Required Travelers")
    for i in range(2):
        selected = st.selectbox(
            f"Person {i+1} (Required)",
            stations_data['Station'].tolist(),
            key=f"station_{i}"
        )
        station = stations_data[stations_data['Station'] == selected].iloc[0]
        users.append((station['Latitude'], station['Longitude']))
    
    # Optional travelers (last 3)
    st.markdown("### Optional Travelers")
    for i in range(2, 5):
        selected = st.selectbox(
            f"Person {i+1} (Optional)",
            ["-- Not Selected --"] + stations_data['Station'].tolist(),
            key=f"station_{i}"
        )
        if selected != "-- Not Selected --":
            station = stations_data[stations_data['Station'] == selected].iloc[0]
            users.append((station['Latitude'], station['Longitude']))

else:  # Coordinates mode
    st.header("Enter Coordinates for All Travelers")
    
    # Required travelers (first 2)
    st.markdown("### Required Travelers")
    for i in range(2):
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(f"Person {i+1} Latitude (Required)", key=f"lat_{i}")
        with col2:
            lon = st.number_input(f"Person {i+1} Longitude (Required)", key=f"lon_{i}")
        users.append((lat, lon))
    
    # Optional travelers (last 3)
    st.markdown("### Optional Travelers")
    for i in range(2, 5):
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(f"Person {i+1} Latitude (Optional)", key=f"lat_{i}")
        with col2:
            lon = st.number_input(f"Person {i+1} Longitude (Optional)", key=f"lon_{i}")
        if lat and lon:  # Only add if both values exist
            users.append((lat, lon))

# API Key (consider using st.secrets in production)
api_key = "f234cac01ae545d2991cc51681a2f820"

if st.button("Find Meeting Point") and len(users) >= 2:
    with st.spinner("Calculating best meeting point..."):
        try:
            stations = load_stations("tube_stations.csv")
            
            # Find nearest stations for all users
            distance_matrix = precompute_distances(stations)
            user_stations = []
            for user in users:
                nearest = None
                min_dist = float('inf')
                for i, station in stations.iterrows():
                    dist = distance_matrix[i][i]  # Using precomputed distances
                    if dist < min_dist:
                        min_dist = dist
                        nearest = station['StationID']
                user_stations.append(nearest)
            
            # Find equal-time station
            best_station = None
            min_variance = float('inf')
            results = {}
            
            for _, dest in stations.iterrows():
                times = []
                valid = True
                
                for start_id in user_stations:
                    time = get_travel_time(start_id, dest['StationID'], api_key)
                    if not time:
                        valid = False
                        break
                    times.append(time)
                
                if valid and len(times) == len(users):
                    mean = sum(times) / len(times)
                    variance = sum((t - mean)**2 for t in times) / len(times)
                    results[dest['Station']] = {
                        'times': times,
                        'variance': variance
                    }
                    if variance < min_variance:
                        min_variance = variance
                        best_station = dest['Station']
            
            if best_station:
                st.success(f"Best meeting point: {best_station}")
                st.write("Travel times:")
                for i, time in enumerate(results[best_station]['times']):
                    st.write(f"User {i+1}: {time} minutes")
            else:
                st.error("Could not find a suitable meeting point")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")

# Add some spacing
st.markdown("---")
st.caption("Note: Uses TfL API for real-time travel data")
