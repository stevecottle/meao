import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import requests
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
        
        # --- Filter only Tube (subway) legs ---
        for leg in legs:
            if leg.get('routeOptions'):
                line_name = leg['routeOptions'][0].get('name', '').strip()
                if line_name:  # Only include tube legs
                    route_details.append({
                        'from': leg['departurePoint']['commonName'],
                        'to': leg['arrivalPoint']['commonName'],
                        'line': line_name
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
    
    try:
        cache_size = len(requests_cache.get_cache().responses)
        st.caption(f"Cache stats: {cache_size} cached responses")
    except:
        st.caption("Cache stats: 0 cached responses")

# --- User Input Section ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.subheader("📍 Starting Stations")
st.caption("Select the tube stations where each person will start from:")

# Load stations
try:
    stations_df = load_stations("tube_stations_complete.csv")
    station_names = sorted(stations_df['Station'].tolist())
except Exception as e:
    st.error(f"Could not load tube_stations_complete.csv file: {e}")
    st.stop()

# Initialize session state
if 'user_stations' not in st.session_state:
    st.session_state.user_stations = []

# --- Dropdown + Add Button (horizontal alignment) ---
st.markdown("<br>", unsafe_allow_html=True)
st.caption("Choose a station:")

# Create columns: dropdown takes more width, button smaller
col1, col2 = st.columns([3, 1])
with col1:
    selected_station = st.selectbox(
        label="Choose a station",
        options=["Select a station..."] + station_names,
        key="station_dropdown",
        label_visibility="collapsed"
    )

with col2:
    if st.button("Add Station", type="secondary"):
        if selected_station != "Select a station..." and selected_station not in st.session_state.user_stations:
            st.session_state.user_stations.append(selected_station)
            st.rerun()

# --- Current Stations Display ---
if st.session_state.user_stations:
    st.markdown("<br>", unsafe_allow_html=True)
    st.write("**Current starting stations:**")
    for i, station in enumerate(st.session_state.user_stations):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"{i+1}. {station}")
        with col2:
            if st.button("Remove", key=f"remove_{i}", type="secondary"):
                st.session_state.user_stations.pop(i)
                st.rerun()

if len(st.session_state.user_stations) < 2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("ℹ️ Add at least 2 starting stations to find a meeting point")

# --- CALCULATION SECTION ---
st.markdown("<br>", unsafe_allow_html=True)
if st.button("Meet everyone at once!", type="primary") and len(st.session_state.user_stations) >= 2:
    with st.spinner("Calculating destination station with equal travel time..."):
        try:
            stations = load_stations("tube_stations_complete.csv")
            users = st.session_state.user_stations
            user_coords = []
            user_station_ids = []
            
            for user_station_name in users:
                row = stations[stations['Station'] == user_station_name]
                if not row.empty:
                    station_data = row.iloc[0]
                    user_coords.append((station_data['Latitude'], station_data['Longitude']))
                    user_station_ids.append(station_data['StationID'])
                else:
                    st.error(f"Could not find station: {user_station_name}")
                    st.stop()
            
            midpoint = (
                sum(c[0] for c in user_coords) / len(user_coords),
                sum(c[1] for c in user_coords) / len(user_coords)
            )
            st.info(f"📍 Geographic center point: {midpoint[0]:.4f}, {midpoint[1]:.4f}")
            
            radius_km = 5
            nearby_stations = [s for _, s in stations.iterrows()
                               if geodesic(midpoint, (s['Latitude'], s['Longitude'])).km <= radius_km]
            
            if not nearby_stations:
                st.warning(f"No stations within {radius_km} km of midpoint.")
                st.stop()
            
            st.info(f"🔍 Checking {len(nearby_stations)} stations within {radius_km} km")
            
            best_station = None
            min_variance = float('inf')
            results = {'times': [], 'routes': []}
            dest_progress = st.progress(0)
            
            for idx, dest in enumerate(nearby_stations):
                dest_progress.progress((idx + 1) / len(nearby_stations))
                times, routes = [], []
                valid = True
                for start_id in user_station_ids:
                    travel_time, route = get_travel_time_with_routes(start_id, dest['StationID'], api_key)
                    if not travel_time:
                        valid = False
                        break
                    times.append(travel_time)
                    routes.append(route)
                if valid and len(times) == len(users):
                    mean_time = sum(times) / len(times)
                    variance = sum((t - mean_time) ** 2 for t in times) / len(times)
                    if variance < min_variance:
                        min_variance = variance
                        best_station = dest['Station']
                        results['times'] = times
                        results['routes'] = routes
            
            dest_progress.empty()
            
            if best_station:
                st.success(f"## 🎯 Meet everyone at: {best_station}")
                st.write("### 🚇 Travel Details")
                
                for i, (time_min, route) in enumerate(zip(results['times'], results['routes'])):
                    st.write(f"#### Person {i+1} from {users[i]}: {time_min} minutes")
                    for j, leg in enumerate(route):
                        if j == 0:
                            st.markdown(f"**Start:** {leg['from']}")
                        else:
                            st.markdown(f"**Change at:** {leg['from']}")
                        st.markdown(f"→ **{leg['to']}** _(via {leg['line']})_")
                    st.markdown("---")
                
                avg_time = sum(results['times']) / len(results['times'])
                max_diff = max(results['times']) - min(results['times'])
                st.info(f"📊 Average travel time: {avg_time:.1f} minutes | Max difference: {max_diff:.1f} minutes")
            else:
                st.error("❌ Couldn't find a suitable meeting station. Try stations closer together or different starting stations.")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if "timed out" in str(e).lower():
                st.info("💡 API might be busy. Try again in a few minutes.")

# --- Clear All Button ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")
st.caption("🚇 Using TfL API for real-time travel data")
