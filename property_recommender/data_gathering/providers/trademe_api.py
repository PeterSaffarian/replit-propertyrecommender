"""
property_recommender/data_gathering/providers/trademe_api.py

This module handles interaction with the Trade Me API, including:
  1. OAuth1 authentication setup (sandbox or production environments).
  2. Fetching and caching of metadata (regions, suburbs, property types, sales methods).
  3. Providing convenience accessors for common metadata types.

Environment Variables (in .env file):
  - TM_ENV:                "sandbox" (default) or "production" to select base URL.
  - TRADEME_CONSUMER_KEY:    Your Trade Me API consumer key.
  - TRADEME_CONSUMER_SECRET: Your Trade Me API consumer secret.

Usage:
  from data_gathering.providers.trademe_api import (
      get_oauth_session, get_regions, get_suburbs,
      get_property_types, get_sales_methods
  )

Example:
  session = get_oauth_session()
  regions = get_regions()
"""

import os
import json
from pathlib import Path

from requests_oauthlib import OAuth1Session
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment switch: 'sandbox' or 'production'
TM_ENV = os.getenv("TM_ENV", "sandbox").lower()
BASE_URL = (
    "https://api.trademe.co.nz/v1"
    if TM_ENV == "production"
    else "https://api.tmsandbox.co.nz/v1"
)

# OAuth1 credentials (from .env)
CONSUMER_KEY = os.getenv("TRADEME_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TRADEME_CONSUMER_SECRET")

# Metadata cache file path
METADATA_CACHE_FILE = Path(__file__).parent / "trademe_metadata.json"


def get_oauth_session() -> OAuth1Session:
    """
    Create and return an OAuth1Session for authenticating Trade Me API calls.

    Raises:
        EnvironmentError: If API credentials are missing.
    """
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        raise EnvironmentError(
            "Missing Trade Me consumer key/secret. Check your .env file."
        )
    return OAuth1Session(
        client_key=CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
    )


def fetch_metadata_from_api(metadata_type: str) -> dict:
    """
    Fetch metadata of the given type directly from the Trade Me API.

    Args:
        metadata_type: One of 'regions', 'suburbs', 'propertytypes', 'salesmethods'.
    Returns:
        Parsed JSON response as a dictionary.
    Raises:
        HTTPError: If the API request fails.
    """
    key = metadata_type.lower()
    if key == "regions":
        url = f"{BASE_URL}/localities/regions.json"
    elif key == "suburbs":
        url = f"{BASE_URL}/localities/suburbs.json"
    elif key == "propertytypes":
        url = f"{BASE_URL}/metadata/propertytypes.json"
    elif key == "salesmethods":
        url = f"{BASE_URL}/metadata/salesmethods.json"
    else:
        raise ValueError(f"Unknown metadata type: {metadata_type!r}")

    session = get_oauth_session()
    response = session.get(url)
    response.raise_for_status()
    return response.json()


def get_metadata(metadata_type: str, force_refresh: bool = False) -> dict:
    """
    Retrieve metadata with optional caching to avoid repeated API calls.

    Args:
        metadata_type: Type of metadata to retrieve (e.g., 'regions').
        force_refresh: If True, ignore cache and fetch fresh data.

    Returns:
        Metadata as a dictionary.
    """
    key = metadata_type.lower()
    cache: dict = {}

    # Load cache if present
    if METADATA_CACHE_FILE.exists() and not force_refresh:
        try:
            cache = json.loads(METADATA_CACHE_FILE.read_text())
        except json.JSONDecodeError:
            cache = {}

    # Fetch fresh if needed
    if force_refresh or key not in cache:
        data = fetch_metadata_from_api(key)
        cache[key] = data
        METADATA_CACHE_FILE.write_text(json.dumps(cache, indent=2))

    return cache[key]


def get_regions(force_refresh: bool = False) -> dict:
    """Get a list of regions."""
    return get_metadata("regions", force_refresh)


def get_suburbs(force_refresh: bool = False) -> dict:
    """Get a list of suburbs."""
    return get_metadata("suburbs", force_refresh)


def get_property_types(force_refresh: bool = False) -> dict:
    """Get a list of property types."""
    return get_metadata("propertytypes", force_refresh)


def get_sales_methods(force_refresh: bool = False) -> dict:
    """Get available sales methods."""
    return get_metadata("salesmethods", force_refresh)


# End of trademe_api.py
