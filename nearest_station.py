from geopy.distance import geodesic

def find_nearest_station(user_coords, stations):
    """
    Find the nearest Tube station to the user's coordinates.
    
    Args:
        user_coords (tuple): A tuple of (latitude, longitude) for the user.
        stations (pd.DataFrame): A DataFrame containing Tube station data.
    
    Returns:
        str: The name of the nearest station.
    """
    nearest_station = None
    min_distance = float('inf')  # Start with a very large distance
    
    for _, station in stations.iterrows():
        station_coords = (station['Latitude'], station['Longitude'])
        distance = geodesic(user_coords, station_coords).km  # Distance in kilometers
        if distance < min_distance:
            min_distance = distance
            nearest_station = station['Station']
    
    return nearest_station

# Example usage
if __name__ == "__main__":
    import pandas as pd
    
    # Load the station data
    stations = pd.read_csv("tube_stations.csv")
    
    # Example user coordinates (latitude, longitude)
    user_coords = (51.5074, -0.1278)  # Central London
    
    # Find the nearest station
    nearest_station = find_nearest_station(user_coords, stations)
    print(f"Nearest Station: {nearest_station}")