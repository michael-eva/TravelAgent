from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict
import googlemaps
import requests
import os
import re
from datetime import datetime, timedelta

class GoogleRoutesInput(BaseModel):
    origin: str = Field(default="", description="Starting location (leave empty to use current location)")
    destination: str = Field(description="Destination location")
    waypoints: Optional[List[str]] = Field(default=None, description="List of stops along the route")
    mode: str = Field(default="driving", description="Travel mode (driving/walking/bicycling/transit)")

class GoogleRoutesTool(BaseTool):
    name: str = "google_routes"
    description: str = (
        "Get optimized directions between locations with multiple stops using Google Maps Routes API. "
        "Automatically optimizes waypoint order for the most efficient route. "
        "If no origin is specified, will use user's current location if available. "
        "Input: origin (optional), destination, optional waypoints list, and travel mode."
    )
    gmaps: Any = Field(default=None, exclude=True)
    api_key: str = Field(default="", exclude=True)
    user_context: Dict = Field(default_factory=dict, exclude=True)
    
    def __init__(self, user_context: Dict = None):
        super().__init__()
        self.api_key = os.getenv("GPLACES_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API key not found in GPLACES_API_KEY environment variable")
        self.gmaps = googlemaps.Client(key=self.api_key)
        self.args_schema = GoogleRoutesInput
        self.user_context = user_context or {}
    
    def _geocode_location(self, location: str) -> Optional[Dict[str, float]]:
        """Convert address to lat/lng using Google Geocoding API"""
        try:
            geocode_result = self.gmaps.geocode(location)
            if geocode_result:
                location_data = geocode_result[0]['geometry']['location']
                return {
                    'latitude': location_data['lat'], 
                    'longitude': location_data['lng']
                }
            return None
        except Exception as e:
            print(f"Geocoding error for {location}: {e}")
            return None
    
    def _format_duration(self, duration_seconds: int) -> str:
        """Format duration from seconds to human readable format"""
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _format_distance(self, distance_meters: int) -> str:
        """Format distance from meters to human readable format"""
        if distance_meters >= 1000:
            return f"{distance_meters / 1000:.1f} km"
        else:
            return f"{distance_meters} m"
    
    def _get_current_location_coords(self) -> Optional[Dict[str, float]]:
        """Get current location coordinates from user context"""
        if not self.user_context or 'current_location' not in self.user_context:
            return None
        
        location = self.user_context['current_location']
        
        # Check if location is still valid (within 30 minutes)
        if 'timestamp' in location:
            time_diff = datetime.now() - location['timestamp']
            if time_diff > timedelta(minutes=30):
                return None  # Location too old
        
        return {
            'latitude': location['latitude'],
            'longitude': location['longitude']
        }
    
    def _get_current_location_address(self) -> str:
        """Get readable address for current location"""
        coords = self._get_current_location_coords()
        if not coords:
            return "Current Location"
        
        try:
            result = self.gmaps.reverse_geocode((coords['latitude'], coords['longitude']))
            if result:
                return result[0]['formatted_address']
            return f"Current Location ({coords['latitude']:.4f}, {coords['longitude']:.4f})"
        except:
            return f"Current Location ({coords['latitude']:.4f}, {coords['longitude']:.4f})"
    
    def _call_routes_api(self, origin_coords: Dict[str, float], dest_coords: Dict[str, float], 
                        intermediate_coords: List[Dict[str, float]], mode: str) -> Dict:
        """Call Google Routes API v2"""
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.api_key,
            'X-Goog-FieldMask': 'routes.duration,routes.distanceMeters,routes.legs.duration,routes.legs.distanceMeters,routes.legs.startLocation,routes.legs.endLocation,routes.optimizedIntermediateWaypointIndex'
        }
        
        # Build intermediates array
        intermediates = []
        for coords in intermediate_coords:
            intermediates.append({
                "location": {
                    "latLng": {
                        "latitude": coords['latitude'],
                        "longitude": coords['longitude']
                    }
                }
            })
        
        # Map mode to API format
        travel_mode_map = {
            'driving': 'DRIVE',
            'walking': 'WALK',
            'bicycling': 'BICYCLE',
            'transit': 'TRANSIT'
        }
        
        data = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin_coords['latitude'],
                        "longitude": origin_coords['longitude']
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": dest_coords['latitude'],
                        "longitude": dest_coords['longitude']
                    }
                }
            },
            "travelMode": travel_mode_map.get(mode.lower(), 'DRIVE')
        }
        
        # Add intermediates and optimization if waypoints exist
        if intermediates:
            data["intermediates"] = intermediates
            data["optimizeWaypointOrder"] = True
        
        response = requests.post(url, headers=headers, json=data)
        return response.json()
    
    def _create_google_maps_url(self, origin_coords: Dict[str, float], dest_coords: Dict[str, float], 
                               waypoints: Optional[List[str]] = None) -> str:
        """Create Google Maps URL for the route"""
        origin_str = f"{origin_coords['latitude']},{origin_coords['longitude']}"
        dest_str = f"{dest_coords['latitude']},{dest_coords['longitude']}"
        
        if waypoints:
            # Add waypoints to the URL
            waypoint_coords = []
            for waypoint in waypoints:
                coords = self._geocode_location(waypoint)
                if coords:
                    waypoint_coords.append(f"{coords['latitude']},{coords['longitude']}")
            
            if waypoint_coords:
                waypoints_str = "|".join(waypoint_coords)
                return f"https://www.google.com/maps/dir/{origin_str}/{waypoints_str}/{dest_str}"
        
        return f"https://www.google.com/maps/dir/{origin_str}/{dest_str}"
    
    def _run(self, origin: str = "", destination: str = "", waypoints: Optional[List[str]] = None, 
             mode: str = "driving") -> str:
        try:
            # Determine origin coordinates
            origin_coords = None
            origin_address = origin
            using_current_location = False
            
            if not origin:
                # Try to use current location
                origin_coords = self._get_current_location_coords()
                if origin_coords:
                    origin_address = self._get_current_location_address()
                    using_current_location = True
                else:
                    return "❌ No origin specified and no current location available. Please share your location or specify a starting point."
            else:
                # Geocode the provided origin
                origin_coords = self._geocode_location(origin)
                if not origin_coords:
                    return f"❌ Could not find coordinates for origin '{origin}'"
            
            # Geocode destination
            dest_coords = self._geocode_location(destination)
            if not dest_coords:
                return f"❌ Could not find coordinates for destination '{destination}'"
            
            # Geocode waypoints if provided
            intermediate_coords = []
            failed_waypoints = []
            
            if waypoints:
                for waypoint in waypoints:
                    coords = self._geocode_location(waypoint)
                    if coords:
                        intermediate_coords.append(coords)
                    else:
                        failed_waypoints.append(waypoint)
            
            # Warn about failed waypoints but continue
            result = ""
            if failed_waypoints:
                result = f"⚠️ Could not find: {', '.join(failed_waypoints)}\n\n"
            
            # Call Routes API
            api_response = self._call_routes_api(origin_coords, dest_coords, intermediate_coords, mode)
            
            if 'error' in api_response:
                return f"❌ Routes API Error: {api_response['error'].get('message', 'Unknown error')}"
            
            if 'routes' not in api_response or not api_response['routes']:
                return "❌ No route found between the specified locations"
            
            route = api_response['routes'][0]
            
            # Build result string
            location_indicator = "📍 Your Location" if using_current_location else "📍 Starting Point"
            result += f"🗺️ **Route Summary**\n"
            result += f"{location_indicator}: {origin_address}\n"
            result += f"🎯 **Destination**: {destination}\n"
            result += f"🚗 **Travel Mode**: {mode.title()}\n\n"
            
            # Show optimization info if waypoints were provided
            if waypoints and 'optimizedIntermediateWaypointIndex' in route:
                optimized_indices = route['optimizedIntermediateWaypointIndex']
                optimized_waypoints = [waypoints[i] for i in optimized_indices if i < len(waypoints)]
                result += f"🔄 **Optimized stops**: {' → '.join(optimized_waypoints)}\n\n"
            
            # Total route info
            if 'duration' in route:
                total_duration = int(route['duration'].rstrip('s'))
                result += f"⏱️ **Total Time**: {self._format_duration(total_duration)}\n"
            
            if 'distanceMeters' in route:
                result += f"📏 **Total Distance**: {self._format_distance(route['distanceMeters'])}\n\n"
            
            # Create Google Maps link
            maps_url = self._create_google_maps_url(origin_coords, dest_coords, waypoints)
            result += f"🔗 **[Open in Google Maps]({maps_url})**\n\n"
            
            # Show route summary (not detailed turn-by-turn)
            if 'legs' in route and len(route['legs']) > 1:
                result += "📋 **Route Breakdown**:\n"
                for i, leg in enumerate(route['legs']):
                    if i == 0 and using_current_location:
                        leg_start = "📍 Your Location"
                    else:
                        leg_start = origin_address if i == 0 else f"Stop {i}"
                    
                    if i == len(route['legs']) - 1:
                        leg_end = f"🎯 {destination}"
                    else:
                        leg_end = f"Stop {i+1}"
                    
                    result += f"• **Leg {i+1}**: {leg_start} → {leg_end}"
                    
                    if 'duration' in leg:
                        leg_duration = int(leg['duration'].rstrip('s'))
                        result += f" ({self._format_duration(leg_duration)})"
                    
                    if 'distanceMeters' in leg:
                        result += f" - {self._format_distance(leg['distanceMeters'])}"
                    
                    result += "\n"
            
            result += f"\n✅ **Route ready!** Click the Google Maps link above for turn-by-turn navigation."
            
            return result
            
        except requests.exceptions.RequestException as e:
            return f"❌ Network error calling Routes API: {str(e)}"
        except Exception as e:
            return f"❌ Unexpected error: {str(e)}"

# For backward compatibility, also support the old method signature
def create_routes_tool_with_context(user_context: Dict = None):
    """Factory function to create GoogleRoutesTool with user context"""
    return GoogleRoutesTool(user_context=user_context)