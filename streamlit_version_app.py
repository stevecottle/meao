import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import requests
import numpy as np
import time
import requests_cache  # <-- NEW: Import caching library

# --- NEW: Configure API Caching ---
requests_cache.install_cache(
    'tfl_api_cache',           # Cache file name
    expire_after=3600,         # Cache expires after 1 hour (3600 seconds)
    allowable_methods=['GET'], # Only cache GET requests
    stale_if_error=True        # Use cached data if API fails
)

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
    # --- NEW: Create unique cache key ---
    cache_key = f"{start_station_id}_{end_station_id}"
    
    # --- NEW: Check session cache first ---
    if 'api_cache' in st.session_state and cache_key in st.session_state.api_cache:
        return st.session_state.api_cache[cache_key]
    
    if start_station_id == end_station_id:
        return None, []
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    # --- NEW: Optimized API parameters ---
    params = {
        "app_key": api_key,
        "mode": "tube",
        "maxChange": 1,
        "timeIs": "Departing",   # Faster calculation mode
        "walkingSpeed": "Fast",  # Optimize walking routes
        "date": time.strftime("%Y%m%d"),  # Current date
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)  # Reduced timeout from 10 to 5
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
        
        # --- NEW: Cache successful results ---
        if duration:  # Only cache valid responses
            if 'api_cache' not in st.session_state:
                st.session_state.api_cache = {}
            st.session_state.api_cache[cache_key] = (duration, route_details)
        
        return duration, route_details
    
    except requests.exceptions.Timeout:
        if retries > 0:
            time.sleep(1)
            return get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries - 1)
        st.warning(f"Timeout getting data for {start_station_id}→{end_station_id}")
        return None, []
    except Exception as e:
        st.error(f"API Error: {e}")
        return None, []

# --- Streamlit UI ---
st.title("🚇 Meet everyone at once, London!")

# --- NEW: Cache Management UI ---
with st.expander("⚙️ Cache Settings"):
    if st.button("Clear API Cache"):
        requests_cache.clear()
        if 'api_cache' in st.session_state:
            del st.session_state.api_cache
        st.success("Cache cleared!")
    st.caption(f"Cache stats: {len(requests_cache.get_cache().responses)} cached responses")

# --- API Key Input ---
st.subheader("🔑 TfL API Configuration")
api_key = st.text_input(
    "Enter your TfL API Key", 
    type="password", 
    help="Get your free API key from https://api-portal.tfl.gov.uk/"
)

if not api_key:
    st.warning("⚠️ Please enter your TfL API key to continue")
    st.stop()

# --- User Input Section ---
st.subheader("📍 Starting Locations")
st.write("Add the tube stations where each person will start from:")

# Initialize users list in session state
if 'users' not in st.session_state:
    st.session_state.users = []

# Add user interface
col1, col2 = st.columns([3, 1])
with col1:
    new_station = st.text_input("Station name (e.g., 'King's Cross St. Pancras')", key="station_input")
with col2:
    if st.button("Add Station"):
        if new_station and new_station not in st.session_state.users:
            st.session_state.users.append(new_station)
            # Clear the input by rerunning
            st.rerun()

# Display current users
users = st.session_state.users  # This is the variable that was missing!

if users:
    st.write("**Current starting stations:**")
    for i, user in enumerate(users):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"{i+1}. {user}")
        with col2:
            if st.button("Remove", key=f"remove_{i}"):
                st.session_state.users.pop(i)
                st.rerun()

# Show minimum requirement
if len(users) < 2:
    st.info("ℹ️ Add at least 2 starting stations to find a meeting point")

# --- CALCULATION SECTION ---
if st.button("Meet everyone at once") and len(users) >= 2:
    with st.spinner("Calculating destination station with equal travel time..."):
        try:
            stations = load_stations("tube_stations.csv")
            
            # --- NEW: Limit destination stations for performance ---
            if len(stations) > 30:
                stations = stations.sample(30)  # Check max 30 random stations
                st.info("Checking 30 random stations for faster results")
            
            # Find nearest stations for all users
            distance_matrix = precompute_distances(stations)
            user_stations = []
            
            # --- NEW: Progress bar for station finding ---
            progress_bar = st.progress(0)
            for idx, user in enumerate(users):
                nearest = None
                min_dist = float('inf')
                for i, station in stations.iterrows():
                    dist = distance_matrix[i][i]
                    if dist < min_dist:
                        min_dist = dist
                        nearest = station['StationID']
                user_stations.append(nearest)
                progress_bar.progress((idx + 1) / len(users))
            progress_bar.empty()
            
            # Find equal-time station
            best_station = None
            min_variance = float('inf')
            results = {'times': [], 'routes': []}
            
            # --- NEW: Progress bar for destination checking ---
            dest_progress = st.progress(0)
            for idx, (_, dest) in enumerate(stations.iterrows()):
                dest_progress.progress((idx + 1) / len(stations))
                
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
            
            dest_progress.empty()

            if best_station:
                st.success(f"## Meet everyone at once here!: {best_station}")
                st.write("### Travel Details")
                for i, (time, route) in enumerate(zip(results['times'], results['routes'])):
                    st.write(f"#### Person {i+1}: {time} minutes")
                    for j, leg in enumerate(route):
                        st.write(f"{j+1}. From **{leg['from']}** → **{leg['to']}** (via {leg['line']})")
                    st.write("---")
            else:
                st.error("We couldn't find a suitable station. Try these fixes:")
                st.markdown("""
                - Reduce number of starting points
                - Try different stations
                - Check during less busy hours
                """)
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if "timed out" in str(e).lower():
                st.info("Tip: The API might be busy. Try again in a few minutes.")

# Add some spacing
st.markdown("---")
st.caption("We use TfL API for real-time travel data")
