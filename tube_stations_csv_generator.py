import requests
import csv

# API Setup
api_url = "https://api.tfl.gov.uk/StopPoint/Mode/tube"
api_key = "f234cac01ae545d2991cc51681a2f820"
headers = {"Content-Type": "application/json"}

# Get data from TfL API
response = requests.get(f"{api_url}?app_key={api_key}", headers=headers)
data = response.json()

# Process stations
stations = []
for stop_point in data["stopPoints"]:
    if stop_point["stopType"] == "NaptanMetroStation":
        station_name = stop_point["commonName"].replace(" Underground Station", "")
        stations.append({
            "Station": station_name,
            "Latitude": stop_point["lat"],
            "Longitude": stop_point["lon"],
            "StationID": stop_point["naptanId"]
        })

# Write to CSV
with open("london_underground_stations.csv", "w", newline="") as csvfile:
    fieldnames = ["Station", "Latitude", "Longitude", "StationID"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(stations)

print("CSV file created successfully!")