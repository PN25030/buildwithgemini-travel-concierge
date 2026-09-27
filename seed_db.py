#!/usr/bin/env python3
"""
Seed script for Travel Concierge agent Firestore database.
"""

from google.cloud import firestore

# CRITICAL: Hardcode GCP project ID as string for Firestore client.
# Do NOT use google.auth.default() or GOOGLE_CLOUD_PROJECT on Agent Platform.
GCP_PROJECT_ID = "qwiklabs-gcp-02-6827f82e03c1"

DESTINATIONS = [
    {
        "id": "dest_paris",
        "name": "Paris",
        "country": "France",
        "description": "The City of Light, famous for world-class art, gastronomy, and iconic architecture.",
        "best_season": "Spring / Autumn",
        "avg_cost_per_day": 180,
        "top_attractions": ["Eiffel Tower", "Louvre Museum", "Montmartre", "Notre-Dame Cathedral"],
    },
    {
        "id": "dest_tokyo",
        "name": "Tokyo",
        "country": "Japan",
        "description": "A bustling metropolis blending ultra-modern skyscrapers with historic temples.",
        "best_season": "Spring / Autumn",
        "avg_cost_per_day": 150,
        "top_attractions": ["Shibuya Crossing", "Senso-ji Temple", "Akihabara", "Tokyo Skytree"],
    },
    {
        "id": "dest_kyoto",
        "name": "Kyoto",
        "country": "Japan",
        "description": "Japan's cultural capital known for classical Buddhist temples, gardens, and traditional wooden houses.",
        "best_season": "Spring / Autumn",
        "avg_cost_per_day": 130,
        "top_attractions": ["Fushimi Inari Shrine", "Arashiyama Bamboo Grove", "Kinkaku-ji"],
    },
    {
        "id": "dest_san_francisco",
        "name": "San Francisco",
        "country": "USA",
        "description": "Famous for its steep rolling hills, iconic Golden Gate Bridge, cable cars, and vibrant culinary scene.",
        "best_season": "Summer / Fall",
        "avg_cost_per_day": 200,
        "top_attractions": ["Golden Gate Bridge", "Alcatraz Island", "Fisherman's Wharf", "Chinatown"],
    },
    {
        "id": "dest_bali",
        "name": "Bali",
        "country": "Indonesia",
        "description": "An Indonesian island known for its forested volcanic mountains, iconic rice paddies, and coral reefs.",
        "best_season": "Dry Season (April - October)",
        "avg_cost_per_day": 70,
        "top_attractions": ["Ubud Rice Terraces", "Uluwatu Temple", "Seminyak Beach", "Mount Batur"],
    },
]

def seed_database():
    print(f"Connecting to Firestore with project ID: {GCP_PROJECT_ID}...")
    db = firestore.Client(project=GCP_PROJECT_ID)
    
    collection_ref = db.collection("destinations")
    print("Seeding destinations...")
    for item in DESTINATIONS:
        doc_ref = collection_ref.document(item["id"])
        doc_ref.set(item)
        print(f"  ✓ Saved: {item['name']} ({item['id']})")
    print("Successfully seeded Firestore database!")

if __name__ == "__main__":
    seed_database()
