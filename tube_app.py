import pandas as pd
from geopy.distance import geodesic
import requests
import time  # Add this import at the top of the file

# Load station data
def load_stations(filename):
    """Load Tube station data from CSV."""
    return pd.read_csv(filename)

# Find the nearest station
def find_nearest_station(user_coords, stations):
    """Find the nearest station to user coordinates."""
    nearest_station = None
    min_distance = float('inf')
    
    for _, station in stations.iterrows():
        station_coords = (station['Latitude'], station['Longitude'])
        distance = geodesic(user_coords, station_coords).km
        if distance < min_distance:
            min_distance = distance
            nearest_station = station['Station']
    
    return nearest_station

# Get travel time between stations
def get_travel_time(start_station_id, end_station_id, api_key, retries=3):
    """
    Get travel time between stations using TfL API.
    
    Args:
        start_station_id (str): The ID of the starting station.
        end_station_id (str): The ID of the destination station.
        api_key (str): Your TfL API key.
        retries (int): Number of retries for 500 Server Error.
    
    Returns:
        int: Travel time in minutes, or None if the request fails.
    """
    # Skip if start and end stations are the same
    if start_station_id == end_station_id:
        print(f"Skipping: {start_station_id} → {end_station_id} (same station)")
        return None
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {"app_key": api_key, "mode": "tube"}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Check if the response contains journeys
        if 'journeys' not in data or not data['journeys']:
            print(f"No journeys found: {start_station_id} → {end_station_id}")
            return None
            
        return data['journeys'][0]['duration']
    except requests.exceptions.HTTPError as e:
        if response.status_code == 500 and retries > 0:
            print(f"Server error: Retrying {start_station_id} → {end_station_id}... ({retries} retries left)")
            time.sleep(1)  # Wait 1 second before retrying
            return get_travel_time(start_station_id, end_station_id, api_key, retries - 1)
        else:
            print(f"Error fetching travel time: {e}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Find the equal-time destination
def find_equal_time_station(users, stations, api_key):
    """Find destination station with most equal travel times."""
    user_stations = [find_nearest_station(user, stations) for user in users]
    
    travel_times = {}
    for _, destination in stations.iterrows():
        dest_id = destination['StationID']
        times = []
        valid = True
        
        for start_station in user_stations:
            start_id = stations[stations['Station'] == start_station]['StationID'].values[0]
            time = get_travel_time(start_id, dest_id, api_key)
            if not time:
                valid = False
                break
            times.append(time)
        
        if valid:
            travel_times[destination['Station']] = times
    
    # Find station with minimum time variance
    best_station = None
    min_variance = float('inf')
    
    for station, times in travel_times.items():
        mean = sum(times) / len(times)
        variance = sum((t - mean) ** 2 for t in times) / len(times)
        if variance < min_variance:
            min_variance = variance
            best_station = station
    
    return best_station

# Main script
if __name__ == "__main__":
    # Load station data
    stations = load_stations("tube_stations.csv")
    
    # Example users (latitude, longitude)
    users = [
        (51.531804, -0.118101),  # Near Kings Cross St Pancras
        (51.493619, -0.175627),  # Near South Kensington
    ]
    
    # TfL API key
    api_key = "f234cac01ae545d2991cc51681a2f820"  # Replace with your key
    
    # Find the equal-time destination
    result = find_equal_time_station(users, stations, api_key)
    if result:
        print(f"\nEqual-time destination: {result}")
    else:
        print("\nUnable to find an equal-time destination.")