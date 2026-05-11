# tools.py

TOOL_SCHEMAS = [
    {
        "name": "get_context",
        "description": "Retrieve information from the LORE graph using specific keywords.",
        "risk_level": "low",
        "requires_confirmation": False,
        "parameters": {
            "type": "object",
            "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
            "required": ["keywords"]
        }
    },
    {
        "name": "update_memory",
        "description": "Updates or adds a specific trait or preference for a person or object in the home database.",
        "risk_level": "moderate",
        "requires_confirmation": False,
        "parameters": {
            "type": "object",
            "properties": {
                "target_uid": {
                    "type": "string",
                    "description": "The unique ID of the person or object (e.g., 'dad', 'child_1')."
                },
                "key": {
                    "type": "string",
                    "description": "The trait being updated (e.g., 'favorite_color', 'bedtime', 'role')."
                },
                "value": {
                    "type": "string",
                    "description": "The new value for the trait."
                }
            },
            "required": ["target_uid", "key", "value"]
        }
    },
    {
        "name": "control_home",
        "description": "Triggers an action in the smart home via Home Assistant.",
        "risk_level": "low",
        "requires_confirmation": False,
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string", 
                    "description": "The HA domain (e.g., 'light', 'switch', 'climate', 'media_player')."
                },
                "service": {
                    "type": "string",
                    "description": "The action to take (e.g., 'turn_on', 'turn_off', 'toggle', 'set_temperature')."
                },
                "entity_id": {
                    "type": "string",
                    "description": "The specific device ID in Home Assistant (e.g., 'light.kitchen_main')."
                },
                "brightness": {
                    "type": "integer",
                    "description": "Optional: Brightness level from 0 to 255 (for lights)."
                },
                "color_name": {
                    "type": "string",
                    "description": "Optional: CSS color name (e.g., 'red', 'blue', 'purple') for RGB lights."
                },
                "temperature": {
                    "type": "integer",
                    "description": "Optional: Target temperature in Celsius (for climate devices)."
                },
                "volume_level": {
                    "type": "number",
                    "description": "Optional: Float from 0.0 to 1.0 (for media players)."
                }
            },
            "required": ["domain", "service", "entity_id"]
        }
    },
    {
        "name": "read_document",
        "description": "Reads the text content of a local file (markdown, txt, or json) to gather deep project lore or complex instructions.",
        "risk_level": "low",
        "requires_confirmation": False,
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The full system path to the file."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "delete_node",
        "description": "Permanently erase an entity and its relationships from LORE.",
        "risk_level": "critical",
        "requires_confirmation": True,
        "parameters": {
            "type": "object",
            "properties": {"uid": {"type": "string"}},
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