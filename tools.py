# tools.py - The "Manual" for the LLM

TOOL_SCHEMAS = [
    {
        "name": "update_memory",
        "description": "Updates or adds a specific trait or preference for a person or object in the home database.",
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
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string", 
                    "description": "The HA domain (e.g., 'light', 'switch', 'media_player')."
                },
                "service": {
                    "type": "string",
                    "description": "The action to take (e.g., 'turn_on', 'turn_off', 'toggle')."
                },
                "entity_id": {
                    "type": "string",
                    "description": "The specific device ID in Home Assistant (e.g., 'light.kitchen_main')."
                },
                "brightness": {
                    "type": "integer",
                    "description": "Optional brightness level from 0 to 255."
                }
            },
            "required": ["domain", "service", "entity_id"]
        }
    }
    {
        "name": "read_document",
        "description": "Reads the text content of a local file (markdown, txt, or json) to gather deep project lore or complex instructions.",
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
    }
]