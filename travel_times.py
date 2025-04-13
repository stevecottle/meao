import requests

def get_travel_time(start_station_id, end_station_id, api_key):
    """
    Get the travel time between two Tube stations using the TfL API.
    
    Args:
        start_station_id (str): The ID of the starting station.
        end_station_id (str): The ID of the destination station.
        api_key (str): Your TfL API key.
    
    Returns:
        int: Travel time in minutes, or None if the request fails.
    """
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{start_station_id}/to/{end_station_id}"
    params = {
        "app_key": api_key,
        "mode": "tube"  # Restrict to Tube only
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        
        # Print the API response for debugging
        print("API Response:", data)
        
        # Check if the response contains journeys
        if 'journeys' not in data or len(data['journeys']) == 0:
            print(f"No journeys found from {start_station_id} to {end_station_id}.")
            return None
        
        # Extract the travel time (in minutes) from the API response
        travel_time = data['journeys'][0]['duration']
        return travel_time
    except requests.exceptions.RequestException as e:
        print(f"Error fetching travel time: {e}")
        return None
    except KeyError:
        print("Error: Unable to parse travel time from API response.")
        return None

# Example usage
if __name__ == "__main__":
    api_key = "f234cac01ae545d2991cc51681a2f820"  # Replace with your actual API key
    
    # Station IDs for Charing Cross and Waterloo
    start_station_id = "1000045"  # Charing Cross
    end_station_id = "1000254"    # Waterloo
    
    travel_time = get_travel_time(start_station_id, end_station_id, api_key)
    if travel_time:
        print(f"Travel time from Charing Cross to Waterloo: {travel_time} minutes")
    else:
        print("Failed to fetch travel time.")