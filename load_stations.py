import pandas as pd

def load_stations(filename):
    """
    Load the Tube station data from a CSV file.
    
    Args:
        filename (str): Path to the CSV file.
    
    Returns:
        pd.DataFrame: A DataFrame containing station data.
    """
    return pd.read_csv(filename)

# Example usage
if __name__ == "__main__":
    stations = load_stations("tube_stations.csv")
    print(stations.head())  # Print the first few rows to verify