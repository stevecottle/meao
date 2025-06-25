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
def get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries=3):
    if start_station_id == end_station_id:
        return None, []
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {"app_key": api_key, "mode": "tube", "maxChange": 1}  # Limit to 1 change
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'journeys' not in data or not data['journeys']:
            return None, []
            
        # Find the journey with fewest changes
        best_journey = None
        min_changes = float('inf')
        
        for journey in data['journeys']:
            num_changes = len(journey['legs']) - 1
            if num_changes < min_changes:
                min_changes = num_changes
                best_journey = journey
        
        if not best_journey:
            return None, []
        
        duration = best_journey['duration']
        legs = best_journey['legs']
        route_details = []
        
        for leg in legs:
            route_details.append({
                'from': leg['departurePoint']['commonName'],
                'to': leg['arrivalPoint']['commonName'],
                'line': leg['routeOptions'][0]['name'] if leg['routeOptions'] else 'Walking'
            })
        
        return duration, route_details
    except requests.exceptions.HTTPError as e:
        if response.status_code == 500 and retries > 0:
            time.sleep(1)
            return get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries - 1)
        return None, []
    except Exception as e:
        st.error(f"API Error: {e}")
        return None, []

# --- Streamlit UI ---
st.title("🚇 Meet everyone at once, London!")

# Input Mode Selection
input_mode = st.radio(
    "Choose input method:",
    ["Stations", "Coordinates"],
    index=0,
    horizontal=True
)

# Initialize users list
users = []
stations_data = load_stations("tube_stations.csv")

if input_mode == "Stations":
    st.header("Where are you travelling from?")
    
    # Required travelers (first 2)
    st.markdown("### Travellers")
    for i in range(2):
        selected = st.selectbox(
            f"Start station {i+1} (Required)",
            stations_data['Station'].tolist(),
            key=f"station_{i}"
        )
        station = stations_data[stations_data['Station'] == selected].iloc[0]
        users.append((station['Latitude'], station['Longitude']))
    
    # Optional travelers (last 3)
    st.markdown("### More Travellers")
    for i in range(2, 5):
        selected = st.selectbox(
            f"Start station {i+1} (Optional)",
            ["-- Not Selected --"] + stations_data['Station'].tolist(),
            key=f"station_{i}"
        )
        if selected != "-- Not Selected --":
            station = stations_data[stations_data['Station'] == selected].iloc[0]
            users.append((station['Latitude'], station['Longitude']))

else:  # Coordinates mode
    st.header("Use lat/long Coordinates")
    
    # Required travelers (first 2)
    st.markdown("### Travellers")
    for i in range(2):
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(f"Start coordinates {i+1} Latitude (Required)", key=f"lat_{i}")
        with col2:
            lon = st.number_input(f"Start coordinates {i+1} Longitude (Required)", key=f"lon_{i}")
        users.append((lat, lon))
    
    # Optional travelers (last 3)
    st.markdown("### More Travelers")
    for i in range(2, 5):
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(f"Start coordinates {i+1} Latitude (Optional)", key=f"lat_{i}")
        with col2:
            lon = st.number_input(f"Start coordinates {i+1} Longitude (Optional)", key=f"lon_{i}")
        if lat and lon:  # Only add if both values exist
            users.append((lat, lon))

# API Key (consider using st.secrets in production)
api_key = "f234cac01ae545d2991cc51681a2f820"

if st.button("Meet everyone at once") and len(users) >= 2:
    with st.spinner("Calculating destination station with equal travel time (may take a few minutes) ..."):
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
            results = {'times': [], 'routes': []}  # Initialize results with both times and routes
            
            for _, dest in stations.iterrows():
                times = []
                routes = []
                valid = True
                
                for start_id in user_stations:
                    time, route = get_travel_time_with_routes(start_id, dest['StationID'], api_key)
                    if not time:
                        valid = False
                        break
                    times.append(time)
                    routes.append(route)
                
                if valid and len(times) == len(users):
                    mean = sum(times) / len(times)
                    variance = sum((t - mean)**2 for t in times) / len(times)
                    if variance < min_variance:
                        min_variance = variance
                        best_station = dest['Station']
                        results['times'] = times
                        results['routes'] = routes
            
            if best_station:
                st.success(f"## Meet everyone at once here!: {best_station}")
                st.write("### Travel Details")
                for i, (time, route) in enumerate(zip(results['times'], results['routes'])):
                    st.write(f"#### Person {i+1}: {time} minutes")
                    for j, leg in enumerate(route):
                        st.write(f"{j+1}. From **{leg['from']}** → **{leg['to']}** (via {leg['line']})")
                    st.write("---")
            else:
                st.error("We Couldn't find a suitable station, try altering your stations slightly.")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")

# Add some spacing
st.markdown("---")
st.caption("We use TfL API for real-time travel data")
