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

if __name__ == "__main__":
    # Test: Try to get the state of a known entity (e.g., a light or a sensor)
    client = HassClient()
    # Replace 'sun.sun' with an actual entity ID from your HA instance
    state = client.get_entity_state("sun.sun")
    if state:
        print(f"Connection Successful! Sun state is: {state.get('state')}")