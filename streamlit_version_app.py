import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import requests
import numpy as np
import time
import requests_cache

# --- Configure API Caching ---
requests_cache.install_cache(
    'tfl_api_cache',
    expire_after=3600,
    allowable_methods=['GET'],
    stale_if_error=True
)

# --- API Key Configuration ---
api_key = "f234cac01ae545d2991cc51681a2f820"

# --- Cached Data Loading ---
@st.cache_data
def load_stations(filename):
    return pd.read_csv(filename)

# --- TFL API Functions ---
def get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries=3):
    cache_key = f"{start_station_id}_{end_station_id}"
    
    if 'api_cache' in st.session_state and cache_key in st.session_state.api_cache:
        return st.session_state.api_cache[cache_key]
    
    if start_station_id == end_station_id:
        return None, []
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {
        "app_key": api_key,
        "mode": "tube",
        "maxChange": 1,
        "timeIs": "Departing",
        "walkingSpeed": "Fast",
        "date": time.strftime("%Y%m%d"),
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
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
        
        # Cache successful results
        if duration:
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

# --- Cache Management UI ---
with st.expander("⚙️ Cache Settings"):
    if st.button("Clear API Cache"):
        requests_cache.clear()
        if 'api_cache' in st.session_state:
            del st.session_state.api_cache
        st.success("Cache cleared!")
    
    # Show cache stats
    try:
        cache_size = len(requests_cache.get_cache().responses)
        st.caption(f"Cache stats: {cache_size} cached responses")
    except:
        st.caption("Cache stats: 0 cached responses")

# --- User Input Section ---
st.subheader("📍 Starting Locations")
st.write("Select the tube stations where each person will start from:")

# Load stations for dropdown
try:
    stations_df = load_stations("tube_stations.csv")
    # Use the correct column name from your CSV
    station_names = sorted(stations_df['Station'].tolist())
except Exception as e:
    st.error(f"Could not load tube_stations.csv file: {e}")
    st.stop()

# Initialize users list in session state
if 'user_stations' not in st.session_state:
    st.session_state.user_stations = []

# Add user interface
col1, col2 = st.columns([3, 1])
with col1:
    selected_station = st.selectbox(
        "Choose a station:", 
        options=["Select a station..."] + station_names,
        key="station_dropdown"
    )
with col2:
    if st.button("Add Station", type="primary"):
        if selected_station != "Select a station..." and selected_station not in st.session_state.user_stations:
            st.session_state.user_stations.append(selected_station)
            st.rerun()

# Display current stations
if st.session_state.user_stations:
    st.write("**Current starting stations:**")
    for i, station in enumerate(st.session_state.user_stations):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"{i+1}. {station}")
        with col2:
            if st.button("Remove", key=f"remove_{i}", type="secondary"):
                st.session_state.user_stations.pop(i)
                st.rerun()

# Show minimum requirement
if len(st.session_state.user_stations) < 2:
    st.info("ℹ️ Add at least 2 starting stations to find a meeting point")

# --- CALCULATION SECTION ---
if st.button("Meet everyone at once!", type="primary") and len(st.session_state.user_stations) >= 2:
    with st.spinner("Calculating destination station with equal travel time..."):
        try:
            stations = load_stations("tube_stations.csv")
            users = st.session_state.user_stations  # Use the stations from session state
            
            # Get user coordinates and station IDs from selected station names
            user_coords = []
            user_stations = []
            
            for user_station_name in users:
                user_station_row = stations[stations['Station'] == user_station_name]
                if not user_station_row.empty:
                    station_data = user_station_row.iloc[0]
                    user_coords.append((station_data['Latitude'], station_data['Longitude']))
                    user_stations.append(station_data['StationID'])
                else:
                    st.error(f"Could not find station: {user_station_name}")
                    st.stop()
            
            # Calculate geographic center point (midpoint)
            midpoint_lat = sum(coord[0] for coord in user_coords) / len(user_coords)
            midpoint_lon = sum(coord[1] for coord in user_coords) / len(user_coords)
            midpoint = (midpoint_lat, midpoint_lon)
            
            st.info(f"📍 Geographic center point: {midpoint_lat:.4f}, {midpoint_lon:.4f}")
            
            # Find stations within radius of the midpoint
            radius_km = 5  # Fixed radius for now
            nearby_stations = []
            
            for _, station in stations.iterrows():
                station_coords = (station['Latitude'], station['Longitude'])
                distance_to_center = geodesic(midpoint, station_coords).km
                if distance_to_center <= radius_km:
                    nearby_stations.append(station)
            
            if not nearby_stations:
                st.warning(f"No stations found within {radius_km}km of center point. This might be due to your selected stations being very far apart.")
                st.stop()
                
            st.info(f"🔍 Checking {len(nearby_stations)} stations within {radius_km}km radius")
            
            # Find equal-time station from nearby candidates
            best_station = None
            min_variance = float('inf')
            results = {'times': [], 'routes': []}
            
            # Progress bar for destination checking
            dest_progress = st.progress(0)
            for idx, dest_station in enumerate(nearby_stations):
                dest_progress.progress((idx + 1) / len(nearby_stations))
                
                times = []
                routes = []
                valid = True
                
                for start_id in user_stations:
                    travel_time, route = get_travel_time_with_routes(start_id, dest_station['StationID'], api_key)
                    if not travel_time:
                        valid = False
                        break
                    times.append(travel_time)
                    routes.append(route)
                
                if valid and len(times) == len(users):
                    mean_time = sum(times) / len(times)
                    variance = sum((t - mean_time)**2 for t in times) / len(times)
                    if variance < min_variance:
                        min_variance = variance
                        best_station = dest_station['Station']
                        results['times'] = times
                        results['routes'] = routes
            
            dest_progress.empty()

            if best_station:
                st.success(f"## 🎯 Meet everyone at: {best_station}")
                st.write("### 🚇 Travel Details")
                for i, (travel_time, route) in enumerate(zip(results['times'], results['routes'])):
                    st.write(f"#### Person {i+1} from {users[i]}: {travel_time} minutes")
                    for j, leg in enumerate(route):
                        st.write(f"  {j+1}. From **{leg['from']}** → **{leg['to']}** (via {leg['line']})")
                    st.write("---")
                
                # Show summary stats
                avg_time = sum(results['times']) / len(results['times'])
                max_diff = max(results['times']) - min(results['times'])
                st.info(f"📊 Average travel time: {avg_time:.1f} minutes | Maximum difference: {max_diff:.1f} minutes")
            else:
                st.error("❌ Couldn't find a suitable meeting station. Try:")
                st.markdown("""
                - Selecting stations closer to each other
                - Trying different starting stations
                - Checking during less busy hours
                """)
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if "timed out" in str(e).lower():
                st.info("💡 The API might be busy. Try again in a few minutes.")

# Add some spacing
st.markdown("---")
st.caption("🚇 Using TfL API for real-time travel data")

# Clear all button
if st.session_state.user_stations:
    if st.button("🗑️ Clear All Stations"):
        st.session_state.user_stations = []
        st.rerun()
