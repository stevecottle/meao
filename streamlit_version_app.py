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
    ["Coordinates", "Station Names"],
    horizontal=True
)

# Initialize users list
users = []

if input_mode == "Coordinates":
    st.header("Enter User Coordinates")
    cols = st.columns(3)
    for i in range(3):  # For 3 users
        with cols[i]:
            st.subheader(f"User {i+1}")
            lat = st.number_input("Latitude", key=f"lat{i}")
            lon = st.number_input("Longitude", key=f"lon{i}")
            if lat and lon:  # Only add if both values exist
                users.append((lat, lon))
else:
    stations_data = load_stations("tube_stations.csv")
    st.header("Select User Stations")
    cols = st.columns(3)
    for i in range(3):  # For 3 users
        with cols[i]:
            st.subheader(f"User {i+1}")
            selected = st.selectbox(
                "Station",
                stations_data['Station'].tolist(),
                key=f"station{i}"
            )
            if selected:
                station = stations_data[stations_data['Station'] == selected].iloc[0]
                users.append((station['Latitude'], station['Longitude']))

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
