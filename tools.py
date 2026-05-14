# tools.py

TOOL_SCHEMAS = [
    # --- Core Memory Tools ---
    {
        "name": "get_context",
        "description": "Fetch LORE graph data by keyword.",
        "risk_level": "low",
        "parameters": {
            "type": "object",
            "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
            "required": ["keywords"]
        }
    },
    {
        "name": "modify_lore",
        "description": "Omni-tool to update memory. Add/update nodes, link entities, or delete nodes.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "upsert_nodes": {
                    "type": "array", 
                    "items": {"type": "object", "properties": {"uid": {"type": "string"}, "traits": {"type": "object"}}}
                },
                "create_links": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"source": {"type": "string"}, "target": {"type": "string"}, "relation": {"type": "string"}}}
                },
                "delete_uids": {
                    "type": "array", 
                    "items": {"type": "string"}
                }
            }
        }
    },
    # --- Home Assistant Tools ---
    {
        "name": "control_home",
        "description": "Execute action on HASS entity.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "e.g., 'light', 'switch'"},
                "service": {"type": "string", "description": "e.g., 'turn_on', 'turn_off'"},
                "entity_id": {"type": "string"},
                "kwargs": {"type": "object", "description": "Optional params like brightness, color."}
            },
            "required": ["domain", "service", "entity_id"]
        }
    },
    {
        "name": "inspect_entity",
        "description": "Get HASS entity state. Provide start_time_iso for history.",
        "risk_level": "low",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "start_time_iso": {"type": "string", "description": "Optional ISO 8601 timestamp."}
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "get_area_map",
        "description": "Get structural map of the home.",
        "risk_level": "low",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "fire_home_event",
        "description": "Trigger custom Home Assistant event.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "event_name": {"type": "string"},
                "event_data": {"type": "object"}
            },
            "required": ["event_name"]
        }
    }
]

def get_tool_schema(tool_name):
    """Fetches the schema and safety flags for a given tool."""
    for tool in TOOL_SCHEMAS:
        if tool["name"] == tool_name:
            return tool
    return None