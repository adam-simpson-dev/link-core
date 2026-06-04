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
        "description": "Omni-tool to batch update memory. Mint nodes, link entities, delete nodes, or sever relationships using the Hybrid Schema.",
        "risk_level": "moderate",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_reasoning": {
                    "type": "string", 
                    "description": "Brief explanation of logical deductions made to execute these changes."
                },
                "upsert_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "uid": {"type": "string", "description": "Immutable primary key (e.g., button_k2so_stop)"},
                            "node_type": {"type": "string", "enum": ["hardware", "security_hardware", "routine", "location", "person", "pet", "concept"]},
                            "display_name": {"type": "string"},
                            "aliases": {"type": "array", "items": {"type": "string"}},
                            "new_traits": {"type": "object"},
                            "new_pointers": {"type": "object"}
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
                "delete_links": {
                    "type": "array",
                    "description": "Sever specific edges between nodes without deleting the nodes themselves.",
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
                },
                "rename_uids": {
                    "type": "array",
                    "description": "Migrate an immutable node UID to a clean, descriptive identifier while completely preserving its structural links and JSON payloads.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_uid": {"type": "string"},
                            "new_uid": {"type": "string"}
                        },
                        "required": ["old_uid", "new_uid"]
                    }
                },
                "merge_uids": {
                    "type": "array",
                    "description": "Folds multiple redundant nodes into a single master node. Automatically aggregates all pointers and aliases, re-routes edges, and deletes the targets.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_uids": {"type": "array", "items": {"type": "string"}, "description": "List of UIDs to absorb and delete (e.g., ['person_nickname'])"},
                            "master_uid": {"type": "string", "description": "The UID that will survive and inherit the data (e.g., 'person_name_surname')"},
                            "display_name": {"type": "string"}
                        },
                        "required": ["target_uids", "master_uid", "display_name"]
                    }
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