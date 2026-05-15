import logging
from core_logger import setup_core_logger
import requests
import os
from dotenv import load_dotenv

# Load the secrets from the .env file
load_dotenv()

logger = logging.getLogger(__name__)

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
            logger.error(f"[!] Failed to get state for {entity_id}: {response.status_code}")
            return None

    def call_service(self, domain, service, service_data=None):
        """Triggers an action in Home Assistant (e.g., light.turn_on)."""
        endpoint = f"{self.url}/api/services/{domain}/{service}"
        response = requests.post(endpoint, headers=self.headers, json=service_data)
        
        if response.status_code == 200:
            logger.info(f"[*] Service {domain}.{service} executed successfully.")
            return True
        else:
            logger.error(f"[!] Service call failed: {response.text}")
            return False

    def fire_custom_event(self, event_name, event_data={}):
        """Triggers a HASS automation without needing specific entity IDs."""
        url = f"{self.url}/api/events/{event_name}"
        response = requests.post(url, headers=self.headers, json=event_data)
        if response.status_code in [200, 201]:
            logger.info(f"[*] Event {event_name} fired successfully.")
            return True
        logger.error(f"[!] Event {event_name} failed: {response.status_code}")
        return False

    def get_history(self, entity_id, start_time_iso):
        """
        Retrieves state history for a specific entity. 
        Example start_time_iso: '2026-05-14T10:00:00Z'
        """
        url = f"{self.url}/api/history/period/{start_time_iso}?filter_entity_id={entity_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            logger.warning(f"[!] Failed to fetch history for {entity_id}: {response.status_code}")
            return []
        return response.json()

    def get_area_registry(self):
        """
        Executes a server-side Jinja2 template to extract topography.
        Returns a clean dictionary: {"Kitchen": ["light.main", "sensor.motion"], ...}
        """
        template = """
        {%- set ns = namespace(areas={}) -%}
        {%- for area in areas() -%}
          {%- set entities = area_entities(area) -%}
          {%- if entities -%}
            {%- set ns.areas = dict(ns.areas, **{area_name(area): entities}) -%}
          {%- endif -%}
        {%- endfor -%}
        {{ ns.areas | tojson }}
        """
        endpoint = f"{self.url}/api/template"
        try:
            response = requests.post(endpoint, headers=self.headers, json={"template": template})
            if response.status_code == 200:
                import json
                return json.loads(response.text)
            else:
                logger.error(f"[!] Area template failed: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"[!] HASS Template connection error: {e}")
            return {}

    def get_all_states(self):
        """Retrieves the state registry of all entities currently known to Home Assistant."""
        endpoint = f"{self.url}/api/states"
        response = requests.get(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"[!] Failed to pull state registry: {response.status_code} - {response.text}")
            return []