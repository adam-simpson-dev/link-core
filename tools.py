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
        "description": "Omni-tool to batch update memory. Mint nodes, link entities, or delete nodes using the Hybrid Schema.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "upsert_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "uid": {"type": "string", "description": "Immutable primary key (e.g., loc_kitchen, user_john)"},
                            "node_type": {"type": "string", "enum": ["hardware", "person", "location", "concept", "routine", "security_hardware"]},
                            "display_name": {"type": "string", "description": "Clean GUI string"},
                            "aliases": {"type": "array", "items": {"type": "string"}},
                            "new_traits": {"type": "object", "description": "Squishy memory sandbox"},
                            "new_pointers": {"type": "object", "description": "Volatile execution IDs"}
                        },
                        "required": ["uid", "node_type"]
                    }
                },
                "create_links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "relation": {"type": "string"}
                        },
                        "required": ["source", "target", "relation"]
                    }
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
        "description": "Execute an action on a physical home asset using its immutable graph UID. Direct entity tracking is handled via underlying abstraction layers.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "The immutable primary key of the target node (e.g., 'node_light_kitchen')."},
                "service": {"type": "string", "description": "The HASS service to invoke (e.g., 'turn_on', 'turn_off', 'toggle')."},
                "kwargs": {"type": "object", "description": "Optional parameters such as brightness, temperature, or color values."}
            },
            "required": ["uid", "service"]
        }
    },
    {
        "name": "inspect_entity",
        "description": "Examine the state parameters or telemetry history of a home asset using its graph UID.",
        "risk_level": "low",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "The immutable primary key of the target asset (e.g., 'node_light_kitchen')."},
                "start_time_iso": {"type": "string", "description": "Optional ISO 8601 baseline string for state records mining."}
            },
            "required": ["uid"]
        }
    },
    {
        "name": "fire_home_event",
        "description": "Trigger a macro configuration script or environmental routine using its graph UID.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "The immutable primary key of the routine node (e.g., 'node_routine_lockdown')."},
                "event_data": {"type": "object", "description": "Optional dynamic execution variables to pass to the sequence payload."}
            },
            "required": ["uid"]
        }
    }
]

def get_tool_schema(tool_name):
    """Fetches the schema and safety flags for a given tool."""
    for tool in TOOL_SCHEMAS:
        if tool["name"] == tool_name:
            return tool
    return None