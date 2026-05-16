# ⚡ LINK-CORE: Autonomous Home Orchestrator

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Graph_Topology-003B57?logo=sqlite&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Semantics-FF6B6B?logo=database&logoColor=white)
![Home Assistant](https://img.shields.io/badge/Home_Assistant-Bridge-41BDF5?logo=homeassistant&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_2.5-Inference-8E75B2?logo=google&logoColor=white)
![WebGL](https://img.shields.io/badge/Three.js-WebGL_GUI-000000?logo=three.js&logoColor=white)
![Status](https://img.shields.io/badge/Status-Phase_15_Complete-brightgreen)

> **A decoupled, Expert System Architecture bridging a Hybrid Knowledge Graph (Spatial + Semantic) with physical Smart Home hardware via LLM Inference.**

---

## 🧠 Overview

**LINK-CORE** is a local-first orchestration engine. Initially designed as the "Nervous System" for advanced home automation via rigid tool calls, it has purposefully evolved into an **Autonomous ReAct (Reasoning & Acting) Agent**. 

By anchoring probabilistic LLM inference (Google Gemini) to a strict deterministic environment, LINK-CORE acts without the typical hallucination risks of standard chatbots. It utilizes a **Hybrid Memory Architecture** (SQLite Graph Topography + ChromaDB Vector Semantics) to maintain context, and a **Dynamic Dispatcher** to execute physical commands via the **Home Assistant REST API**.

## 🏗️ Architecture

The system is strictly decoupled into distinct operational layers to ensure high resilience and mathematical routing:

* **LORE (`database.py` & `vector_memory.py`):** The Hybrid Knowledge Graph. Employs a Strict Identity Envelope (SQLite) for infallible routing, and a Volatile Payload sandbox (ChromaDB) for semantic "squishy" data retrieval. 
* **CORTEX (`inference.py` & `brain.py`):** The Cognition Engine. Translates physical environment data into temporal prompts, enforcing token conservation and context weighting before passing execution to the LLM.
* **HASS (`hass_client.py`):** The Hands. A secure, abstracted bridge to the Home Assistant API for reading states, executing services, and pinging system topography.
* **CORE (`main.py`):** The Orchestrator. Manages the ReAct execution loop, enforces Circuit Breakers against LLM recursive failures, and delegates JSON Tool calls to backend Python methods.
* **PANOPTICON (`index.html`):** The Visualizer. A high-performance 3D WebGL interface (Three.js/d3-force-3d) rendering real-time system topography, telemetry pings, and internal memory logs.

## 🛠️ Tech Stack

* **Language:** Python 3.12
* **Memory Structure:** SQLite (Topological Graph) + ChromaDB (Semantic Vector Search)
* **Cognition:** Google Gemini 2.5 Flash API
* **GUI:** Native HTML5, CSS Flexbox, Three.js, d3-force-3d
* **Environment:** Windows/VS Code (Client) -> Proxmox LXC Debian/Ubuntu (Server)
* **Key Python Libraries:** `fastapi`, `uvicorn`, `requests`, `google-generativeai`, `chromadb`, `spacy` (Planned)

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
    GEMINI_API_KEY=your_gemini_api_key
    CORE_API_URL=[http://127.0.0.1:8000](http://127.0.0.1:8000)
    ```

5. **Boot the Orchestrator:**
    ```bash
    uvicorn api:app --host 0.0.0.0 --port 8000
    ```

**Client Interaction (Remote Console)**
To interact with the live server offline or diagnose memory faults, run `python dev_console.py` to launch the native CLI Uplink.

---

## 🔮 Execution Roadmap

**Foundation & Abstraction**
* [x] Phase 1: SQLite Graph Memory (LORE)
* [x] Phase 2: Home Assistant Bridge (HASS)
* [x] Phase 3: Dynamic Tool Dispatcher (CORE)
* [x] Phase 4: Proxmox LXC Deployment & Systemd Daemon
* [x] Phase 5: FastAPI Bridge & Decoupled Architecture

**Cognition & UI Integration**
* [x] Phase 6: Neural Pathways (Context Engineering)
* [x] Phase 7: The Panopticon (WebGL Visual Dashboard)
* [x] Phase 8: Cortex Integration (The Gemini Inference Bridge)

**Hardening & Scaling (Current)**
* [x] Phase 9-14: Hybrid Schema Migration, Vector Semantic Search (ChromaDB), & Circuit Breakers
* [x] Phase 15: The Strict Envelope, Domain Routing, & High-Performance UI Overhaul
* [ ] Phase 16: Topological Maintenance & System Memory (The Nocturnal Janitor)
* [ ] Phase 17: Expert System Orchestrator (NLP Blackboard Routing & Modular Prompts)

---

*Developed as a demonstration of decoupled architecture, secure API integration, and local-first data processing.*