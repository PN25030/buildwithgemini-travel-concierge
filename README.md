# Travel Concierge AI Agent

An intelligent, multi-tool AI travel assistant built with the **Google Agent Development Kit (ADK)** and deployed on **Agent Platform**. Travel Concierge helps travelers plan custom trips, check real-time weather, discover attractions, calculate budgets, and render interactive UI cards and visual postcards.

---

## 🚀 Features & Wired-Up Capabilities

### 🧠 Google Cloud Services & Vertex AI
- **Vertex AI Memory Bank**: Integrates `PreloadMemoryTool` and an `after_agent_callback` (`add_session_to_memory`) to extract, store, and recall traveler preferences, budget limits, health constraints, and dietary allergies across sessions.
- **Google Cloud Firestore**: Persists destination catalogs, attraction lists, and daily costs in the `destinations` collection via `search_destinations`, `get_destination_details`, and `add_destination`.
- **Google Cloud Storage**: Stores generated postcard images and video clips in a public GCS bucket (`travel-concierge-assets-qwiklabs-gcp-02-6827f82e03c1`) and returns public HTTPS URLs.
- **Agent Engine Sandbox**: Executes Python code in an isolated `AgentEngineSandboxCodeExecutor` for complex budget math, itinerary calculations, and data processing.
- **Multimodal Gemini Models**:
  - `gemini-2.5-flash`: Primary reasoning model for turn-by-turn dialogue and tool execution.
  - `gemini-3.1-flash-lite-image`: Generates custom scenic travel postcards (`generate_destination_image`).
  - `gemini-omni-flash-preview`: Generates short video clips (`generate_destination_video`).

### 🎨 Rich Dynamic UI (A2UI)
- Built using `A2uiSchemaManager` (v0.8) and `BasicCatalog` with an `after_model_callback` (`a2ui_callback`).
- Dynamically emits structured JSON surfaces (Card, Column, Row, Text, Image) rendered natively in ADK Web (`adk web`) and the custom FastAPI frontend proxy.

### 🌐 Live External APIs & Location Tools
- **Live Weather**: Fetches real-time temperature and weather conditions via `get_live_weather` (Open-Meteo API).
- **Currency Conversion**: Converts currency amounts using official ECB exchange rates via `convert_currency` (Frankfurter API).
- **Google Maps Places & Geocoding**: Resolves addresses to coordinates via `geocode_address` and finds nearby attractions using `find_nearby_places` (Google Maps Places API `searchNearby`).

---

## 📌 Status of Planned Features

- **Live Flight & Hotel Booking Engine Integration**: *Planned, not yet implemented* (currently estimated using budget calculations in the Code Sandbox).

---

## 📁 Project Structure

```text
travel-concierge/
├── app/
│   ├── agent.py               # Root ADK Agent, tools, Memory Bank, Firestore, & A2UI setup
│   ├── a2ui_utils.py          # A2UI callback and component parser
│   └── __init__.py            # Module exports
├── frontend/
│   ├── main.py                # FastAPI proxy (browser -> proxy -> A2A protocol agent)
│   ├── static/index.html      # Custom chat frontend with A2UI renderer
│   ├── Procfile               # Cloud Run deployment entrypoint
│   └── requirements.txt       # Frontend dependencies
├── agents-cli-manifest.yaml   # Agent manifest configuration (v1.1.0, A2A enabled)
├── pyproject.toml             # Project python dependencies
└── GEMINI.md                  # Development guidance & instructions
```

---

## 🛠️ Local Development & Setup Instructions

### Prerequisites
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager
- `google-agents-cli` installed (`uv tool install google-agents-cli`)
- `gcloud` authenticated to your GCP project (`gcloud auth login` & `gcloud auth application-default login`)

### 1. Install Dependencies
```bash
agents-cli install
```

### 2. Run the Agent Playground Locally
Start the ADK development web UI to test agent tools, memory persistence, and A2UI cards:
```bash
adk web
```
*(Or use `agents-cli playground`)*

### 3. Run the Custom Frontend & FastAPI Proxy
To run the custom chat web UI locally:
```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_NUMBER>/locations/<REGION>/reasoningEngines/<RESOURCE_ID>"
export AGENT_DIRECTORY="app"
uv run python main.py
```
Open a browser and navigate to port `8080` on your machine.

---

## 🚀 Deployment Instructions

### Deploy Agent to Agent Runtime
Deploy the agent to Agent Platform:
```bash
agents-cli deploy
```

### Deploy Custom Frontend to Cloud Run
Deploy the FastAPI frontend proxy and UI to Cloud Run:
```bash
cd frontend
gcloud run deploy travel-concierge-frontend \
  --source=. \
  --region=us-east1 \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<YOUR_AGENT_ENGINE_RESOURCE_NAME>",AGENT_DIRECTORY="app" \
  --allow-unauthenticated
```
