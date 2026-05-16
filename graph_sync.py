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

    # Fetch the physical device map
    device_map = hass.get_device_map()
    
    # Reverse lookup: entity_id -> device_id
    entity_to_device = {}
    for dev_id, entities in device_map.items():
        for e in entities:
            entity_to_device[e] = dev_id

    # Hybrid Grouping Architecture
    grouped_unmapped = {}
    orphaned_entities = []

    # Pass A: The Physical Registry (Fully Dynamic, No Hardcoding)
    for e_id in unmapped_entities:
        dev_id = entity_to_device.get(e_id)
        if dev_id:
            if dev_id not in grouped_unmapped:
                grouped_unmapped[dev_id] = []
            grouped_unmapped[dev_id].append(e_id)
        else:
            orphaned_entities.append(e_id)

    # Pass B: The Lexical Safety Net (Strict Whitelist for Orphans)
    KNOWN_SUFFIXES = [
        "_battery", "_power", "_linkquality", "_firmware", "_energy",
        "_voltage", "_current", "_temperature", "_humidity", "_action",
        "_illuminance", "_identify", "_state", "_status", "_occupancy",
        "_contact", "_tamper", "_on_off_transition_time", "_power_on_behavior",
        "_startup_behavior", "_device_temperature"
    ]

    for e_id in orphaned_entities:
        domain, name = e_id.split(".", 1)
        base_name = name
        
        # Only strip if it matches a known, safe diagnostic suffix
        for suffix in KNOWN_SUFFIXES:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break 
                
        group_key = f"lex_{base_name}"
        if group_key not in grouped_unmapped:
            grouped_unmapped[group_key] = []
        grouped_unmapped[group_key].append(e_id)

    # Mint Nodes & Dynamic Payload Packing
    new_nodes_count = 0
    for group_key, entity_group in grouped_unmapped.items():
        # The Shortest Name Wins logic dictates the primary entity
        entity_group.sort(key=len)
        primary_entity = entity_group[0]
        primary_domain, primary_name = primary_entity.split(".", 1)
        
        # Extract the true hardware root (Prevents "Battery" from hijacking headless multi-sensors)
        base_name = primary_name
        for suffix in KNOWN_SUFFIXES:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
                break
                
        uid = f"node_{primary_domain}_{base_name}"
        
        # Clean the UI display name
        raw_friendly = physical_entities[primary_entity].get("attributes", {}).get("friendly_name") or base_name.replace("_", " ").title()
        friendly_name = raw_friendly
        for display_suffix in [" Battery", " Power", " Temperature", " Humidity", " Identify", " Firmware", " Linkquality"]:
            if friendly_name.endswith(display_suffix):
                friendly_name = friendly_name[:-len(display_suffix)]
                break

        # Dynamically build the JSON pointers
        pointers = {}
        for child in entity_group:
            c_domain, c_name = child.split(".", 1)
            
            # Subtract the true base name to find the specific component dynamically
            if c_name.startswith(base_name) and c_name != base_name:
                suffix = c_name.replace(base_name, "").strip("_")
            else:
                # Fallback if strings diverge wildly despite sharing a HA device ID
                suffix = c_name.replace(primary_name, "").strip("_") if c_name.startswith(primary_name) else ""
            
            key_prefix = suffix if suffix else c_domain
            pointers[f"{key_prefix}_id"] = child

        db.upsert_lore(
            uid=uid,
            node_type="hardware" if primary_domain not in ["script", "automation", "scene"] else "routine",
            display_name=friendly_name,
            new_pointers=pointers,
            new_traits={"sync_status": "auto_sorted", "domain": primary_domain}
        )

        # --- THE DOMAIN ROUTER ---
        target_area_uid = None
        for e in entity_group:
            if entity_to_area.get(e):
                target_area_uid = entity_to_area.get(e)
                break
        
        if target_area_uid:
            db.create_relationship(uid, target_area_uid, "located_in")
        elif primary_domain in ["script", "scene", "automation"]:
            db.upsert_lore("sys_logic", "concept", "System Logic")
            db.create_relationship(uid, "sys_logic", "is_logic_for")
        elif primary_domain in ["input_boolean", "input_number", "input_text", "input_select", "input_button", "timer", "todo"]:
            db.upsert_lore("sys_helpers", "concept", "System Helpers")
            db.create_relationship(uid, "sys_helpers", "is_helper_for")
        elif primary_domain in ["sun", "weather", "zone", "person", "device_tracker"]:
            db.upsert_lore("sys_environment", "concept", "Environment & Tracking")
            db.create_relationship(uid, "sys_environment", "tracks")
        elif primary_domain in ["notify", "tts", "stt", "conversation", "event"]:
            db.upsert_lore("sys_services", "concept", "System Services")
            db.create_relationship(uid, "sys_services", "provides_service")
        elif primary_domain in ["update", "sensor", "binary_sensor"]:
            db.upsert_lore("sys_diagnostics", "concept", "System Diagnostics")
            db.create_relationship(uid, "sys_diagnostics", "monitors")
        else:
            db.create_relationship(uid, "unassigned_inbox", "requires_triage")
            
        new_nodes_count += 1

    logger.info(f"[*] Sync Complete: Collapsed registry into {new_nodes_count} distinct nodes.")

if __name__ == "__main__":
    sync_hardware_graph()