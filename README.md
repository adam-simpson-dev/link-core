# ⚡ LINK-CORE: Home Automation Orchestrator

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Graph_Memory-003B57?logo=sqlite&logoColor=white)
![Home Assistant](https://img.shields.io/badge/Home_Assistant-Bridge-41BDF5?logo=homeassistant&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-LXC_Deployed-E57000?logo=proxmox&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API_Bridge-009688?logo=fastapi&logoColor=white)
![Status](https://img.shields.io/badge/Status-Phase_5_Complete-brightgreen)

> **A decoupled, Brain-Agnostic architecture bridging a localized Knowledge Graph with physical Smart Home hardware.**

---

## 🧠 Overview

**LINK-CORE** is a local-first orchestration engine. It acts as the "Nervous System" for advanced home automation, designed to accept dynamic Tool Calls (from manual input or a future LLM) and translate them into physical actions. 

Instead of relying on rigid, procedural `if/else` scripts, the system utilizes a **Triadic Graph Memory (SQLite)** to maintain context and a **Dynamic Dispatcher** to execute commands via the **Home Assistant REST API**.

## 🏗️ Architecture

The system is separated into three distinct modules to ensure high resilience and ease of swapping components (like future LLMs):

*   **LORE (`database.py`):** The Knowledge Graph. Uses an Upsert pattern to store Entities (Nodes), Relationships (Edges), and Context (Properties). Flattens graph data into LLM-readable context strings.
*   **HASS (`hass_client.py`):** The Hands. A secure bridge to the Home Assistant REST API for reading device states and triggering services.
*   **CORE (`api.py` & `main.py`):** The Orchestrator. A FastAPI server that maps incoming JSON Tool Schemas (defined in `tools.py`) to internal Python methods, allowing any remote "Brain" to control the system.

## 🛠️ Tech Stack

*   **Language:** Python 3.12
*   **Database:** SQLite (Relational structure acting as a Graph Database)
*   **Environment:** Windows/VS Code (Client) -> Proxmox LXC Debian/Ubuntu (Server)
*   **Key Libraries:** `fastapi`, `uvicorn`, `requests`, `python-dotenv`

## 🚀 Installation (Local Development)

To run the Developer Console and test the bridge manually:

1. **Clone the repository:**
    ```bash
    git clone [https://github.com/adam-simpson-dev/link-core.git](https://github.com/adam-simpson-dev/link-core.git)
    cd link-core
    ```

2. **Set up the Virtual Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Configure Secrets:**
    Create a `.env` file in the root directory:
    ```text
    HASS_URL=http://YOUR_HA_IP:8123
    HASS_TOKEN=your_long_lived_access_token
    ```

5. **Run the Developer Console:**
    ```bash
    uvicorn api:app --host 0.0.0.0 --port 8000
    ```

**Client Interaction (Remote Console)**
To interact with the live server from a remote machine:

1. Ensure requests and python-dotenv are installed locally.

2. Set CORE_API_URL=http://[LXC_IP]:8000 in your local .env.

3. Run python dev_console.py to dispatch commands over HTTP.

---

🔮 Roadmap

[x] Phase 1: SQLite Graph Memory (LORE)

[x] Phase 2: Home Assistant Bridge (HASS)

[x] Phase 3: Dynamic Tool Dispatcher (CORE)

[x] Phase 4: Proxmox LXC Deployment & Systemd Daemon

[x] Phase 5: FastAPI Bridge & Decoupled Architecture

[ ] Phase 6: Neural Pathways (Context Engineering) - Prepare the data structures required for an LLM to understand time, state, and history.

[ ] Phase 7: The Panopticon (Visual Dashboard) - Construct a read-only web interface to monitor the LORE graph, system state, and active memory queue.

[ ] Phase 8: Cortex Integration (The Inference Bridge) - Connect the AI API key and hand over autonomous execution capabilities.

---

*Developed as a demonstration of decoupled architecture, secure API integration, and local-first data processing.*