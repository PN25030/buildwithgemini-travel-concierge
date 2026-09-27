# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

load_dotenv()

# CRITICAL: Hardcode GCP project ID and Storage Bucket name as strings.
# Do NOT use google.auth.default() or GOOGLE_CLOUD_PROJECT on Agent Platform.
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-6827f82e03c1"
GCS_BUCKET_NAME = "travel-concierge-assets-qwiklabs-gcp-02-6827f82e03c1"
MEMORY_BANK_ID = "5210237608600272896"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, extract durable facts, preferences, and user allergies into Vertex AI Memory Bank."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Memory extraction notice: {e}")
    return None


def get_agent_engine_resource_name() -> str:
    """Retrieve the Agent Engine (ReasoningEngine) resource name from deployment_metadata.json."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    metadata_path = os.path.join(base_dir, "..", "deployment_metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                data = json.load(f)
                runtime_id = data.get("remote_agent_runtime_id")
                if runtime_id:
                    return runtime_id
        except Exception:
            pass
    return f"projects/41528821410/locations/us-central1/reasoningEngines/{MEMORY_BANK_ID}"


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_destinations(query: str = "", max_budget_per_day: int = None) -> list[dict]:
    """Search for travel destinations in the Firestore database.

    Args:
        query: Optional search keyword to filter by destination name, country, or description.
        max_budget_per_day: Optional maximum daily budget in USD.

    Returns:
        List of matching destination dictionaries.
    """
    db = get_firestore_client()
    docs = db.collection("destinations").stream()
    results = []
    query_lower = query.lower() if query else ""

    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue

        # Budget filter
        if max_budget_per_day is not None and data.get("avg_cost_per_day", 0) > max_budget_per_day:
            continue

        # Keyword filter
        if query_lower:
            text = f"{data.get('name', '')} {data.get('country', '')} {data.get('description', '')}".lower()
            if query_lower not in text:
                continue

        results.append(data)
    return results


def get_destination_details(destination_id: str) -> dict:
    """Get full details for a specific travel destination from Firestore.

    Args:
        destination_id: Unique ID of the destination (e.g. 'dest_paris', 'dest_tokyo').

    Returns:
        Destination details dictionary or an error message.
    """
    db = get_firestore_client()
    doc_ref = db.collection("destinations").document(destination_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {"error": f"Destination with ID '{destination_id}' not found."}


def add_destination(
    destination_id: str,
    name: str,
    country: str,
    description: str,
    avg_cost_per_day: int,
    top_attractions: list[str],
    best_season: str = "Year-round",
) -> str:
    """Add a new travel destination or update an existing one in the Firestore database.

    Args:
        destination_id: Unique identifier for the destination (e.g. 'dest_london').
        name: Name of the city or destination.
        country: Country where the destination is located.
        description: Short overview of the destination.
        avg_cost_per_day: Estimated average daily cost in USD.
        top_attractions: List of key attractions or landmarks.
        best_season: Best time of year to visit.

    Returns:
        Success message confirming destination was saved.
    """
    db = get_firestore_client()
    dest_data = {
        "id": destination_id,
        "name": name,
        "country": country,
        "description": description,
        "avg_cost_per_day": avg_cost_per_day,
        "top_attractions": top_attractions,
        "best_season": best_season,
    }
    db.collection("destinations").document(destination_id).set(dest_data)
    return f"Successfully saved destination '{name}' ({destination_id}) to Firestore."


def get_live_weather(location: str) -> dict:
    """Fetch real-time weather and temperature for any city/destination via Open-Meteo API.

    Args:
        location: City or destination name (e.g. 'Kyoto', 'Paris', 'San Francisco').

    Returns:
        Dictionary containing temperature (°C and °F), wind speed, and location details.
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())

        results = geo_data.get("results")
        if not results:
            return {"error": f"Could not find coordinates for location '{location}'."}

        first_match = results[0]
        lat, lon = first_match["latitude"], first_match["longitude"]
        city_name = first_match.get("name", location)
        country = first_match.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req = urllib.request.Request(weather_url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            weather_data = json.loads(resp.read().decode())

        current = weather_data.get("current_weather", {})
        temp_c = current.get("temperature")
        return {
            "location": f"{city_name}, {country}".strip(", "),
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None,
            "windspeed_kmh": current.get("windspeed"),
            "is_daytime": bool(current.get("is_day", 1)),
        }
    except Exception as e:
        return {"error": f"Failed to fetch live weather for '{location}': {str(e)}"}


def convert_currency(amount: float, from_currency: str = "USD", to_currency: str = "EUR") -> dict:
    """Convert a monetary amount from one currency to another using official ECB exchange rates via Frankfurter API.

    Args:
        amount: The monetary amount to convert (e.g. 150.0).
        from_currency: 3-letter currency code for source currency (e.g. 'USD', 'EUR', 'GBP').
        to_currency: 3-letter currency code for target currency (e.g. 'JPY', 'EUR', 'GBP', 'CAD').

    Returns:
        Dictionary with original amount, converted amount, rate, base, target, and date.
    """
    try:
        from_curr = from_currency.strip().upper()
        to_curr = to_currency.strip().upper()

        if from_curr == to_curr:
            return {
                "original_amount": amount,
                "converted_amount": amount,
                "rate": 1.0,
                "from_currency": from_curr,
                "to_currency": to_curr,
            }

        url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        rates = data.get("rates", {})
        converted = rates.get(to_curr)
        if converted is None:
            return {"error": f"Currency conversion from '{from_curr}' to '{to_curr}' not supported."}

        rate = round(converted / amount, 4) if amount > 0 else 0
        return {
            "original_amount": amount,
            "converted_amount": round(converted, 2),
            "rate": rate,
            "from_currency": from_curr,
            "to_currency": to_curr,
            "date": data.get("date"),
        }
    except Exception as e:
        return {"error": f"Failed to convert currency: {str(e)}"}


def geocode_address(address: str) -> dict:
    """Turn an address or landmark into geographic coordinates (latitude, longitude) using Google Maps Geocoding API.

    Args:
        address: Full street address, landmark, or city name (e.g. 'Paris', 'Tokyo', 'Mountain View').

    Returns:
        Dictionary containing formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        # Graceful fallback to Open-Meteo Geocoding if API key is placeholder
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(address)}&count=1&language=en&format=json"
            req = urllib.request.Request(geo_url, headers={"User-Agent": "TravelConcierge/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                geo_data = json.loads(resp.read().decode())
            results = geo_data.get("results", [])
            if results:
                res = results[0]
                return {
                    "name": res.get("name", address),
                    "address": f"{res.get('name', address)}, {res.get('country', '')}".strip(", "),
                    "location": {"latitude": res.get("latitude"), "longitude": res.get("longitude")},
                }
            return {"error": f"No coordinates found for '{address}'. Replace GOOGLE_MAPS_API_KEY in .env with your valid Google Maps API key."}
        except Exception as e:
            return {"error": f"Geocoding error: {str(e)}"}

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return {"error": f"Geocoding API error: {data.get('status')} - {data.get('error_message', 'No results found')}"}

        result = data["results"][0]
        loc = result["geometry"]["location"]
        return {
            "name": address,
            "address": result.get("formatted_address", address),
            "location": {"latitude": loc.get("lat"), "longitude": loc.get("lng")},
        }
    except Exception as e:
        return {"error": f"Failed to geocode address: {str(e)}"}


def find_nearby_places(latitude: float, longitude: float, place_type: str = "tourist_attraction", radius_meters: float = 1000.0) -> list[dict]:
    """Find nearby places of a given type near coordinates using Google Places API (New) searchNearby REST endpoint.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
        place_type: Type of place to search for (e.g. 'tourist_attraction', 'restaurant', 'cafe', 'museum', 'lodging').
        radius_meters: Search radius in meters (default 1000m).

    Returns:
        List of dictionaries containing name, address, and location for each place.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or api_key == "PASTE_KEY_HERE":
        return [{"error": "GOOGLE_MAPS_API_KEY is not set in environment or .env file."}]

    endpoint = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "TravelConcierge/1.0",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": float(radius_meters),
            }
        },
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        places = data.get("places", [])
        results = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "")
            address = p.get("formattedAddress", "")
            loc = p.get("location", {})
            results.append({
                "name": display_name,
                "address": address,
                "location": {"latitude": loc.get("latitude"), "longitude": loc.get("longitude")},
            })
        return results
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return [{"error": f"Places API HTTP error {e.code}: {error_body}"}]
    except Exception as e:
        return [{"error": f"Failed to search nearby places: {str(e)}"}]


async def generate_destination_image(
    destination: str,
    style_prompt: str = "A vibrant travel postcard with iconic scenery and warm lighting",
    tool_context: ToolContext = None,
) -> dict:
    """Generate a scenic travel image/postcard for a destination using gemini-3.1-flash-lite-image in the global region, save it as an artifact, and upload to public GCS.

    Args:
        destination: Name of the destination or city (e.g. 'Kyoto', 'Paris', 'Santorini').
        style_prompt: Optional visual style prompt or scene description.
        tool_context: Optional ToolContext automatically passed by ADK.

    Returns:
        Dictionary with destination, image_url, and status.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT_ID,
            location="global",
        )
        prompt = f"A beautiful travel postcard for {destination}. {style_prompt}"
        resp = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            ),
        )

        img_bytes = None
        mime_type = "image/jpeg"
        for cand in resp.candidates:
            if not cand.content or not cand.content.parts:
                continue
            for part in cand.content.parts:
                if part.inline_data:
                    img_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not img_bytes:
            return {"error": f"No image generated for '{destination}'."}

        ext = "png" if "png" in mime_type else "jpg"
        filename = f"{destination.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}.{ext}"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        if tool_context:
            try:
                artifact_part = types.Part.from_bytes(
                    data=img_bytes,
                    mime_type=mime_type,
                )
                await tool_context.save_artifact(
                    filename=filename,
                    artifact=artifact_part,
                )
            except Exception as artifact_err:
                print(f"Warning: Could not save artifact to tool_context: {artifact_err}")

        # 2. Upload same image bytes to public Cloud Storage bucket
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(img_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "destination": destination,
            "filename": filename,
            "image_url": public_url,
            "status": "Image generated successfully, saved to Playground artifacts, and uploaded to Cloud Storage.",
        }
    except Exception as e:
        return {"error": f"Failed to generate image for '{destination}': {str(e)}"}


async def generate_destination_video(
    destination: str,
    prompt_description: str = "A scenic short clip showing landmarks, culture, and nature",
    tool_context: ToolContext = None,
) -> dict:
    """Generate a short video snippet for a travel destination or landmark using Google's Omni model (gemini-omni-flash-preview) in the global region, save it as an artifact, and upload it to public GCS.

    Args:
        destination: City, landmark, or resort name (e.g. 'Tokyo', 'Hawaii', 'Paris').
        prompt_description: Visual description or scene details for the video generation.
        tool_context: Optional ToolContext automatically provided by ADK.

    Returns:
        Dictionary containing destination, video_url, filename, and status.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT_ID,
            location="global",
        )
        prompt = f"A short 5 second cinematic video of {destination}. {prompt_description}"
        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        # Extract video bytes from output_video or interaction steps
        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                if isinstance(data, str):
                    import base64
                    video_bytes = base64.b64decode(data)
                elif isinstance(data, bytes):
                    video_bytes = data

        if not video_bytes and hasattr(interaction, "steps") and interaction.steps:
            for step in interaction.steps:
                if hasattr(step, "content") and step.content:
                    for item in step.content:
                        data = getattr(item, "data", None)
                        if data and (getattr(item, "type", "") == "video" or getattr(item, "mime_type", "").startswith("video/")):
                            if isinstance(data, str):
                                import base64
                                video_bytes = base64.b64decode(data)
                            elif isinstance(data, bytes):
                                video_bytes = data
                            break

        if not video_bytes:
            return {"error": f"No video bytes returned by gemini-omni-flash-preview for '{destination}'."}

        filename = f"{destination.lower().replace(' ', '_')}_video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact with tool_context.save_artifact so it shows up in Playground's Artifacts panel
        if tool_context:
            try:
                artifact_part = types.Part.from_bytes(
                    data=video_bytes,
                    mime_type="video/mp4",
                )
                await tool_context.save_artifact(
                    filename=filename,
                    artifact=artifact_part,
                )
            except Exception as artifact_err:
                print(f"Warning: Could not save video artifact to tool_context: {artifact_err}")

        # 2. Upload video bytes to public Cloud Storage bucket and return public https URL
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "destination": destination,
            "filename": filename,
            "video_url": public_url,
            "status": "Video generated successfully with gemini-omni-flash-preview, saved to Playground artifacts, and uploaded to Cloud Storage.",
        }
    except Exception as e:
        return {"error": f"Failed to generate video for '{destination}': {str(e)}"}


def get_current_time(query: str) -> str:
    """Simulates getting current time for a city.

    Args:
        query: City name.

    Returns:
        Formatted current time.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


# Build A2UI system prompt using A2uiSchemaManager version 0.8 and BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Travel Concierge, an AI travel assistant. "
        "Pay special attention to user dietary restrictions, health requirements, and allergies "
        "(e.g. food, environmental, or drug allergies). Always extract, remember, recall, and respect "
        "these allergy constraints across all sessions when suggesting travel, dining, hotels, or activities. "
        "Use your tools to search destinations in Firestore, add new travel spots, "
        "fetch live weather, convert currencies, turn addresses into coordinates, "
        "find nearby attractions, generate destination images and videos, "
        "and execute Python code in the Agent Engine sandbox for math or data calculations."
    ),
    workflow_description="Analyze the user's travel request and return structured UI cards when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property (\'h1\', \'h2\', \'body\') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or \'kind\'/\'data\'/\'metadata\' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        vertexai=True,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=get_agent_engine_resource_name()
    ),
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        add_destination,
        get_live_weather,
        convert_currency,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
