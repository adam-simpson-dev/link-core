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
        uid="concept_unassigned_inbox", 
        node_type="concept", 
        display_name="Unassigned Hardware Inbox",
        aliases=["inbox", "new hardware", "unassigned devices"]
    )

    new_nodes_count = 0
    for entity_id in unmapped_entities:
        domain = entity_id.split(".")[0]
        uid = f"node_{entity_id.replace('.', '_')}"
        friendly_name = physical_entities[entity_id].get("attributes", {}).get("friendly_name") or entity_id
        
        # Enforce the strict Envelope and populate the Payload
        db.upsert_lore(
            uid=uid,
            node_type="hardware",
            display_name=friendly_name,
            new_pointers={"hass_id": entity_id},
            new_traits={"sync_status": "unassigned", "domain": domain}
        )
        
        # Topology Routing: Link to the room if HASS knows it, otherwise dump in the inbox
        target_area_uid = entity_to_area.get(entity_id)
        if target_area_uid:
            db.create_relationship(uid, target_area_uid, "located_in")
        else:
            db.create_relationship(uid, "concept_unassigned_inbox", "requires_triage")
            
        new_nodes_count += 1

    logger.info(f"[*] Sync Complete: Minted {new_nodes_count} hardware stubs and mapped spatial topology.")

if __name__ == "__main__":
    sync_hardware_graph()