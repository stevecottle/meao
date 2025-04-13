import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from geopy.distance import geodesic
import requests
import time
import json
import threading
import numpy as np

# Load station data
def load_stations(filename):
    return pd.read_csv(filename)

# Cache for storing API results
travel_time_cache = {}

def load_cache():
    global travel_time_cache
    try:
        with open("travel_time_cache.json", "r") as f:
            travel_time_cache = json.load(f)
    except FileNotFoundError:
        travel_time_cache = {}

def save_cache():
    with open("travel_time_cache.json", "w") as f:
        json.dump(travel_time_cache, f)

# Load cache at startup
load_cache()

# Load station data and API key
stations = load_stations("tube_stations.csv")
api_key = "f234cac01ae545d2991cc51681a2f820"  # Replace with your key

# Precompute distances
def precompute_distances(stations):
    num_stations = len(stations)
    distance_matrix = np.zeros((num_stations, num_stations))
    
    for i, station1 in stations.iterrows():
        for j, station2 in stations.iterrows():
            coords1 = (station1['Latitude'], station1['Longitude'])
            coords2 = (station2['Latitude'], station2['Longitude'])
            distance_matrix[i][j] = geodesic(coords1, coords2).km
    
    return distance_matrix

# Save the distance matrix to a file
distance_matrix = precompute_distances(stations)
np.save("distance_matrix.npy", distance_matrix)

# Load the distance matrix from a file
distance_matrix = np.load("distance_matrix.npy")

# Find the nearest station using precomputed distances
def find_nearest_station(user_coords, stations, distance_matrix):
    nearest_station = None
    min_distance = float('inf')
    
    for i, station in stations.iterrows():
        station_coords = (station['Latitude'], station['Longitude'])
        distance = distance_matrix[i][i]  # Use precomputed distances
        if distance < min_distance:
            min_distance = distance
            nearest_station = station['Station']
    
    return nearest_station

# Get travel time and route details between stations
def get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries=3):
    cache_key = f"{start_station_id}_{end_station_id}"
    if cache_key in travel_time_cache:
        return travel_time_cache[cache_key]
    
    if start_station_id == end_station_id:
        return None, []
    
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {"app_key": api_key, "mode": "tube", "maxChange": 1}  # Limit to 1 change
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'journeys' not in data or not data['journeys']:
            return None, []
            
        # Find the journey with the fewest changes
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
        
        travel_time_cache[cache_key] = (duration, route_details)
        save_cache()
        return duration, route_details
    except requests.exceptions.HTTPError as e:
        if response.status_code == 500 and retries > 0:
            time.sleep(1)
            return get_travel_time_with_routes(start_station_id, end_station_id, api_key, retries - 1)
        else:
            return None, []
    except Exception as e:
        return None, []

# Parallelize API calls
def get_travel_time_parallel(start_station_id, end_station_id, api_key, result_list, index):
    time, route = get_travel_time_with_routes(start_station_id, end_station_id, api_key)
    result_list[index] = (time, route)

def find_equal_time_station(users, stations, api_key):
    user_stations = [find_nearest_station(user, stations, distance_matrix) for user in users]
    
    travel_times = {}
    route_details = {}
    
    threads = []
    results = [None] * len(stations)
    
    for i, (_, destination) in enumerate(stations.iterrows()):
        dest_id = destination['StationID']
        times = []
        routes = []
        valid = True
        
        for start_station in user_stations:
            start_id = stations[stations['Station'] == start_station]['StationID'].values[0]
            thread = threading.Thread(
                target=get_travel_time_parallel,
                args=(start_id, dest_id, api_key, results, i)
            )
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        for result in results:
            if result is None:
                valid = False
                break
            time, route = result
            times.append(time)
            routes.append(route)
        
        if valid:
            travel_times[destination['Station']] = times
            route_details[destination['Station']] = routes
    
    best_station = None
    min_variance = float('inf')
    
    for station, times in travel_times.items():
        mean = sum(times) / len(times)
        variance = sum((t - mean) ** 2 for t in times) / len(times)
        if variance < min_variance:
            min_variance = variance
            best_station = station
    
    return best_station, travel_times.get(best_station, []), route_details.get(best_station, [])

# Function to toggle input mode
def toggle_input_mode():
    if input_mode.get() == 1:  # Latitude/Longitude mode
        # Show lat/long inputs
        label_user1_lat.grid()
        entry_user1_lat.grid()
        label_user1_lon.grid()
        entry_user1_lon.grid()
        label_user2_lat.grid()
        entry_user2_lat.grid()
        label_user2_lon.grid()
        entry_user2_lon.grid()
        label_user3_lat.grid()
        entry_user3_lat.grid()
        label_user3_lon.grid()
        entry_user3_lon.grid()
        
        # Hide dropdowns
        label_user1_station.grid_remove()
        combo_user1_station.grid_remove()
        label_user2_station.grid_remove()
        combo_user2_station.grid_remove()
        label_user3_station.grid_remove()
        combo_user3_station.grid_remove()
    else:  # Dropdown mode
        # Show dropdowns
        label_user1_station.grid()
        combo_user1_station.grid()
        label_user2_station.grid()
        combo_user2_station.grid()
        label_user3_station.grid()
        combo_user3_station.grid()
        
        # Hide lat/long inputs
        label_user1_lat.grid_remove()
        entry_user1_lat.grid_remove()
        label_user1_lon.grid_remove()
        entry_user1_lon.grid_remove()
        label_user2_lat.grid_remove()
        entry_user2_lat.grid_remove()
        label_user2_lon.grid_remove()
        entry_user2_lon.grid_remove()
        label_user3_lat.grid_remove()
        entry_user3_lat.grid_remove()
        label_user3_lon.grid_remove()
        entry_user3_lon.grid_remove()

# Function to handle form submission
def on_submit():
    try:
        status_var.set("Processing...")
        
        if input_mode.get() == 1:  # Latitude/Longitude mode
            user1_lat = entry_user1_lat.get()
            user1_lon = entry_user1_lon.get()
            user2_lat = entry_user2_lat.get()
            user2_lon = entry_user2_lon.get()
            user3_lat = entry_user3_lat.get()
            user3_lon = entry_user3_lon.get()

            if not validate_coordinates(user1_lat, user1_lon) or \
               not validate_coordinates(user2_lat, user2_lon):
                return

            user1_coords = (float(user1_lat), float(user1_lon))
            user2_coords = (float(user2_lat), float(user2_lon))
            user3_coords = None

            if user3_lat and user3_lon:  # Optional User 3
                if not validate_coordinates(user3_lat, user3_lon):
                    return
                user3_coords = (float(user3_lat), float(user3_lon))
        else:  # Dropdown mode
            user1_station = combo_user1_station.get()
            user2_station = combo_user2_station.get()
            user3_station = combo_user3_station.get()

            if user1_station == "Select Station" or user2_station == "Select Station":
                messagebox.showerror("Error", "Please select stations for User 1 and User 2.")
                return

            user1_coords = (
                stations[stations['Station'] == user1_station]['Latitude'].values[0],
                stations[stations['Station'] == user1_station]['Longitude'].values[0]
            )
            user2_coords = (
                stations[stations['Station'] == user2_station]['Latitude'].values[0],
                stations[stations['Station'] == user2_station]['Longitude'].values[0]
            )
            user3_coords = None

            if user3_station != "Select Station":  # Optional User 3
                user3_coords = (
                    stations[stations['Station'] == user3_station]['Latitude'].values[0],
                    stations[stations['Station'] == user3_station]['Longitude'].values[0]
                )

        users = [user1_coords, user2_coords]
        if user3_coords:
            users.append(user3_coords)

        midpoint = calculate_midpoint(user1_coords, user2_coords)
        filtered_stations = filter_stations_within_radius(midpoint, stations, radius_km=10)
        
        result, times, routes = find_equal_time_station(users, filtered_stations, api_key)

        if result:
            result_text = f"Equal-time destination: {result}\n\nTravel Times:\n"
            for i, time in enumerate(times):
                result_text += f"User {i+1}: {time} minutes\n"
            result_text += "\nRoutes:\n"
            for i, route in enumerate(routes):
                result_text += f"User {i+1}:\n"
                for leg in route:
                    result_text += f"  From {leg['from']} to {leg['to']} via {leg['line']}\n"
            messagebox.showinfo("Result", result_text)
        else:
            messagebox.showinfo("Result", "Unable to find an equal-time destination.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        status_var.set("Ready")

# Initialize the main window
root = tk.Tk()
root.title("Tube App")

# Create radio buttons for input mode selection
input_mode = tk.IntVar(value=1)  # Default to lat/long mode

radio_latlon = tk.Radiobutton(root, text="Use Latitude/Longitude", variable=input_mode, value=1, command=toggle_input_mode)
radio_latlon.grid(row=0, column=0, columnspan=3, sticky="w")

radio_dropdown = tk.Radiobutton(root, text="Use Dropdown", variable=input_mode, value=2, command=toggle_input_mode)
radio_dropdown.grid(row=1, column=0, columnspan=3, sticky="w")

# Create input fields for manual coordinates
label_user1_lat = tk.Label(root, text="User 1 Latitude:")
label_user1_lat.grid(row=2, column=0, sticky="e")
entry_user1_lat = tk.Entry(root)
entry_user1_lat.grid(row=2, column=1)
entry_user1_lat.insert(0, "Enter latitude")

label_user1_lon = tk.Label(root, text="User 1 Longitude:")
label_user1_lon.grid(row=3, column=0, sticky="e")
entry_user1_lon = tk.Entry(root)
entry_user1_lon.grid(row=3, column=1)
entry_user1_lon.insert(0, "Enter longitude")

label_user2_lat = tk.Label(root, text="User 2 Latitude:")
label_user2_lat.grid(row=4, column=0, sticky="e")
entry_user2_lat = tk.Entry(root)
entry_user2_lat.grid(row=4, column=1)
entry_user2_lat.insert(0, "Enter latitude")

label_user2_lon = tk.Label(root, text="User 2 Longitude:")
label_user2_lon.grid(row=5, column=0, sticky="e")
entry_user2_lon = tk.Entry(root)
entry_user2_lon.grid(row=5, column=1)
entry_user2_lon.insert(0, "Enter longitude")

label_user3_lat = tk.Label(root, text="User 3 Latitude (optional):")
label_user3_lat.grid(row=6, column=0, sticky="e")
entry_user3_lat = tk.Entry(root)
entry_user3_lat.grid(row=6, column=1)
entry_user3_lat.insert(0, "Enter latitude")

label_user3_lon = tk.Label(root, text="User 3 Longitude (optional):")
label_user3_lon.grid(row=7, column=0, sticky="e")
entry_user3_lon = tk.Entry(root)
entry_user3_lon.grid(row=7, column=1)
entry_user3_lon.insert(0, "Enter longitude")

# Create dropdown menus for station selection
label_user1_station = tk.Label(root, text="User 1 Station:")
label_user1_station.grid(row=2, column=0, sticky="e")
combo_user1_station = ttk.Combobox(root, values=["Select Station"] + stations['Station'].tolist())
combo_user1_station.grid(row=2, column=1)
combo_user1_station.set("Select Station")  # No default selection

label_user2_station = tk.Label(root, text="User 2 Station:")
label_user2_station.grid(row=3, column=0, sticky="e")
combo_user2_station = ttk.Combobox(root, values=["Select Station"] + stations['Station'].tolist())
combo_user2_station.grid(row=3, column=1)
combo_user2_station.set("Select Station")  # No default selection

label_user3_station = tk.Label(root, text="User 3 Station (optional):")
label_user3_station.grid(row=4, column=0, sticky="e")
combo_user3_station = ttk.Combobox(root, values=["Select Station"] + stations['Station'].tolist())
combo_user3_station.grid(row=4, column=1)
combo_user3_station.set("Select Station")  # No default selection

# Hide dropdowns initially
label_user1_station.grid_remove()
combo_user1_station.grid_remove()
label_user2_station.grid_remove()
combo_user2_station.grid_remove()
label_user3_station.grid_remove()
combo_user3_station.grid_remove()

# Create a submit button
submit_button = tk.Button(root, text="Find Equal-Time Destination", command=on_submit)
submit_button.grid(row=8, column=0, columnspan=3, pady=10)

# Add a status bar
status_var = tk.StringVar()
status_var.set("Ready")
status_bar = tk.Label(root, textvariable=status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
status_bar.grid(row=9, column=0, columnspan=3, sticky="we")

# Run the main loop
root.mainloop()