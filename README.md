# ⚡ LINK-CORE: Autonomous Environment Orchestrator

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Graph_Topology-003B57?logo=sqlite&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Semantics-FF6B6B?logo=database&logoColor=white)
![Home Assistant](https://img.shields.io/badge/Home_Assistant-Hardware_Bridge-41BDF5?logo=homeassistant&logoColor=white)

> **A decoupled, local-first ReAct (Reasoning & Acting) Agent bridging a Hybrid Knowledge Graph with physical Smart Home hardware via LLM Inference.**

---

## 🧠 System Overview

**LINK-CORE** is an advanced local-first orchestration engine. It solves the primary failure condition of standard LLM home assistants—hallucination—by anchoring probabilistic reasoning to a strict, deterministic environmental state.

Instead of relying on a massive, bloated context window, LINK-CORE utilizes a custom **Hybrid RAG (Retrieval-Augmented Generation)** architecture. It merges strict relational topography (SQLite) with semantic vector space (ChromaDB), allowing the system to understand both hard physical routing ("Where is the printer?") and squishy human concepts ("What is the ideal sourdough hydration?"). 

## 🏗️ Architecture & Stack

The system is strictly decoupled into distinct operational domains to ensure high resilience, fault isolation, and API stability.

* **CORE (The Orchestrator):** `FastAPI` / `Python`. Manages the ReAct execution loop, enforces token conservation via Execution Compression, and delegates JSON tool calls to backend Python methods.
* **LORE (Hybrid Knowledge Graph):** `SQLite` + `ChromaDB`. Employs a Strict Identity Envelope for infallible topological routing, paired with a volatile vector sandbox for semantic data retrieval.
* **CORTEX (Cognition & NLP):** `spaCy` + `Google Gemini`. Translates natural language into semantic intents. Intercepts hardware commands via localized NLP before escalating complex logic to the LLM. 
* **HASS (The Actuator):** A secure, abstracted REST client bridging the Orchestrator to the Home Assistant API for bi-directional state polling and service execution.
* **PANOPTICON (The Visualizer):** `Three.js` / `d3-force-3d`. A high-performance WebGL interface rendering real-time system topography, telemetry pings, and active context loads.

---

## 🚀 Quickstart (Docker Deployment)

The fastest way to evaluate the LINK-CORE environment is via the pre-configured Docker pipeline. 

1. **Clone the repository:**
    ```bash
    git clone [https://github.com/adam-simpson-dev/link-core.git](https://github.com/adam-simpson-dev/link-core.git)
    cd link-core
    ```

2. **Configure Secrets:**
    Copy the example environment file and insert your API credentials:
    ```bash
    cp .env.example .env
    ```

3. **Ignite the Core:**
    ```bash
    docker-compose up --build -d
    ```
    The GUI and API endpoints will be instantly available at `http://localhost:8000`. Persistent database memory is automatically mapped to the local `./data` volume.

---

## 🛠️ Local Source Development

For native development and script testing without containerization:

1. **Set up the Virtual Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    python -m spacy download en_core_web_sm
    ```

3. **Boot the Orchestrator:**
    ```bash
    uvicorn api:app --host 0.0.0.0 --port 8000
    ```

**Client Interaction (Remote Console)**
To interact with the live server offline, trigger background daemons, or diagnose memory faults, execute `python dev_console.py` to launch the native CLI Uplink.

---

## 🔬 Ongoing Research & Horizons

The core architecture is stable and deployed. Current R&D is focused on expanding background autonomy and offline capabilities:

* **Nocturnal Janitor & Librarian Daemons:** Autonomous vector radar sweeps that mathematically identify and compress redundant semantic concepts while the user is asleep.
* **Spatial Abstraction:** Decoupling raw hardware entity IDs into human-readable area arrays.
* **SLM Migration:** Optimizing the Prompt Manager and Execution Compression protocols to transition inference from cloud APIs to a localized 8B parameter offline model (e.g., Llama 3).