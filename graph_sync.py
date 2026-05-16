import json
import logging
from core_logger import setup_core_logger
from database import DatabaseManager
from hass_client import HassClient

setup_core_logger()
logger = logging.getLogger(__name__)

def sync_hardware_graph():
    """
    Scans HASS for entities, checks LORE for existing mappings, 
    mints spatial locations, and maps hardware topology.
    """
    db = DatabaseManager()
    hass = HassClient()

    logger.info("[*] Initiating Hardware Synchronization Protocol...")

    # Pull the Physical Reality
    raw_states = hass.get_all_states()
    if not raw_states:
        logger.error("[!] Sync Failed: Unable to retrieve states from Home Assistant.")
        return

    physical_entities = {state["entity_id"]: state for state in raw_states}
    logger.info(f"[*] Discovered {len(physical_entities)} hardware entities in HASS.")

    # Pull Topography via Template Hack
    area_map = hass.get_area_registry()
    logger.info(f"[*] Discovered {len(area_map)} structural areas in HASS.")
    
    # Mint Location Nodes & Build O(1) Lookup Table
    entity_to_area = {}
    for area_name, entities in area_map.items():
        area_uid = f"loc_{area_name.lower().replace(' ', '_')}"
        
        # Enforce Location Envelope
        db.upsert_lore(
            uid=area_uid,
            node_type="location",
            display_name=area_name,
            aliases=[area_name, f"the {area_name.lower()}"]
        )
        
        # Map entities to their new spatial UID
        for entity_id in entities:
            entity_to_area[entity_id] = area_uid

    # Pull the Cognitive Map
    cursor = db.conn.cursor()
    cursor.execute("SELECT uid, system_pointers FROM nodes WHERE node_type = 'hardware'")
    mapped_nodes = cursor.fetchall()

    mapped_hass_ids = set()
    for uid, pointers_json in mapped_nodes:
        try:
            pointers = json.loads(pointers_json) if pointers_json else {}
            if "hass_id" in pointers:
                mapped_hass_ids.add(pointers["hass_id"])
        except json.JSONDecodeError:
            continue

    logger.info(f"[*] Found {len(mapped_hass_ids)} hardware entities currently mapped in LORE.")

    # The Delta Check
    unmapped_entities = [e_id for e_id in physical_entities.keys() if e_id not in mapped_hass_ids]
    
    if not unmapped_entities:
        logger.info("[*] Sync Complete: LORE Graph is perfectly aligned with physical hardware.")
        return

    logger.warning(f"[!] Discovered {len(unmapped_entities)} unmapped hardware entities. Minting stubs...")

    # Mint the Unassigned Inbox
    db.upsert_lore(
        uid="unassigned_inbox", 
        node_type="concept", 
        display_name="Unassigned Hardware Inbox",
        aliases=["inbox", "new hardware", "unassigned devices"]
    )

    # 1. Fetch the physical device map
    device_map = hass.get_device_map()
    
    # 2. Reverse lookup: entity_id -> device_id
    entity_to_device = {}
    for dev_id, entities in device_map.items():
        for e in entities:
            entity_to_device[e] = dev_id

    # 3. Group unmapped entities by their physical hardware
    grouped_unmapped = {}
    for e_id in unmapped_entities:
        dev_id = entity_to_device.get(e_id, e_id) # Fallback to entity_id if it lacks a device_id (e.g. scripts)
        if dev_id not in grouped_unmapped:
            grouped_unmapped[dev_id] = []
        grouped_unmapped[dev_id].append(e_id)

    new_nodes_count = 0
    for dev_id, entity_group in grouped_unmapped.items():
        # Sort by length. The primary entity is almost always the shortest string.
        # e.g., 'sensor.motion' comes before 'sensor.motion_battery'
        entity_group.sort(key=len)
        primary_entity = entity_group[0]
        
        domain = primary_entity.split(".")[0]
        uid = f"node_{primary_entity.replace('.', '_')}"
        friendly_name = physical_entities[primary_entity].get("attributes", {}).get("friendly_name") or primary_entity
        
        # Build the collapsed pointer payload
        pointers = {"hass_id": primary_entity}
        for child in entity_group[1:]:
            # Extract the diagnostic suffix to use as the JSON key (e.g., 'battery', 'illuminance')
            suffix = child.replace(primary_entity, "").strip("_")
            if not suffix: suffix = child.split(".")[1]
            pointers[f"{suffix}_id"] = child

        # Mint the collapsed Node
        db.upsert_lore(
            uid=uid,
            node_type="hardware" if domain not in ["script", "automation", "scene"] else "routine",
            display_name=friendly_name,
            new_pointers=pointers,
            new_traits={"sync_status": "auto_sorted", "domain": domain}
        )
        
        # --- THE DOMAIN ROUTER ---
        target_area_uid = entity_to_area.get(primary_entity)
        
        if target_area_uid:
            db.create_relationship(uid, target_area_uid, "located_in")
        elif domain in ["script", "scene", "automation"]:
            db.upsert_lore("sys_logic", "concept", "System Logic")
            db.create_relationship(uid, "sys_logic", "is_logic_for")
        elif domain in ["input_boolean", "input_number", "input_text", "input_select", "timer"]:
            db.upsert_lore("sys_helpers", "concept", "System Helpers")
            db.create_relationship(uid, "sys_helpers", "is_helper_for")
        elif domain in ["sun", "weather", "zone", "person", "device_tracker"]:
            db.upsert_lore("sys_environment", "concept", "Environment & Tracking")
            db.create_relationship(uid, "sys_environment", "tracks")
        elif domain in ["update", "sensor", "binary_sensor"] and "update" in primary_entity:
            db.upsert_lore("sys_diagnostics", "concept", "System Diagnostics")
            db.create_relationship(uid, "sys_diagnostics", "monitors")
        else:
            db.create_relationship(uid, "unassigned_inbox", "requires_triage")
            
        new_nodes_count += 1

    logger.info(f"[*] Sync Complete: Collapsed {len(unmapped_entities)} entities into {new_nodes_count} hardware nodes.")

if __name__ == "__main__":
    sync_hardware_graph()