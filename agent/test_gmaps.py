# test_gmaps.py
import googlemaps
import os

try:
    api_key = os.getenv("GPLACES_API_KEY")
    if api_key:
        gmaps = googlemaps.Client(key=api_key)
        print("Client created successfully!")
        print(f"Has directions method: {hasattr(gmaps, 'directions')}")
        # Test a simple call
        result = gmaps.directions("Sydney", "Melbourne") # type: ignore
        print("Directions call successful!")
    else:
        print("No API key found")
except Exception as e:
    print(f"Error: {e}")