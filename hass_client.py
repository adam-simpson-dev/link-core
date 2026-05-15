import requests
import os
from dotenv import load_dotenv

# Load the secrets from the .env file
load_dotenv()

class HassClient:
    """
    Communicates with the Home Assistant REST API.
    """
    def __init__(self):
        self.url = os.getenv("HASS_URL")
        self.token = os.getenv("HASS_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "content-type": "application/json",
        }

    def get_entity_state(self, entity_id):
        """Retrieves the current state of a specific device or sensor."""
        endpoint = f"{self.url}/api/states/{entity_id}"
        response = requests.get(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[!] Failed to get state for {entity_id}: {response.status_code}")
            return None

    def call_service(self, domain, service, service_data=None):
        """Triggers an action in Home Assistant (e.g., light.turn_on)."""
        endpoint = f"{self.url}/api/services/{domain}/{service}"
        response = requests.post(endpoint, headers=self.headers, json=service_data)
        
        if response.status_code == 200:
            print(f"[*] Service {domain}.{service} executed successfully.")
            return True
        else:
            print(f"[!] Service call failed: {response.text}")
            return False

    def fire_custom_event(self, event_name, event_data={}):
        """Triggers a HASS automation without needing specific entity IDs."""
        url = f"{self.url}/api/events/{event_name}"
        response = requests.post(url, headers=self.headers, json=event_data)
        return response.status_code in [200, 201]

    def get_history(self, entity_id, start_time_iso):
        """
        Retrieves state history for a specific entity. 
        Example start_time_iso: '2026-05-14T10:00:00Z'
        """
        url = f"{self.url}/api/history/period/{start_time_iso}?filter_entity_id={entity_id}"
        response = requests.get(url, headers=self.headers)
        return response.json() if response.status_code == 200 else []

    def get_area_map(self):
        """
        Retrieves the area registry. 
        Note: This often requires processing the state list or having 
        an admin-level token to hit the registry directly.
        """
        # Shortcut: Fetching states usually includes area_id in attributes
        states = self.get_all_states()
        # Logic to group entities by their 'area_id' attribute
        return states