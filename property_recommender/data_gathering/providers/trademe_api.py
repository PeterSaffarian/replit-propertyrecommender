#!/usr/bin/env python3
"""
property_recommender/data_gathering/providers/trademe_api.py

Trade Me Property API client with OAuth1.0 and built-in metadata fetching.

This module provides:
  1. OAuth1Session setup for sandbox vs. production.
  2. `search_properties` to query listings.
  3. `fetch_metadata` to retrieve and cache:
       - Regions
       - Districts
       - Suburbs
       - Property Attributes
     under data_gathering/metadata/*.json for LLM parameter mapping.
  4. Helpers to load cached metadata into Python dicts.

Usage:
    from property_recommender.data_gathering.providers.trademe_api import (
        search_properties,
        fetch_metadata,
        load_metadata
    )

    # Eagerly fetch metadata (sandbox):
    fetch_metadata(sandbox=True)

    # Load region map for QueryBuilder attachment:
    regions = load_metadata("Region")
"""

import os
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parents[2] / '.env')

import requests
from requests_oauthlib import OAuth1Session
from urllib.parse import urljoin

# ------------------------------------------------------------------------------
# Base URLs
# ------------------------------------------------------------------------------
SANDBOX_BASE = "https://api.tmsandbox.co.nz/v1/"
PROD_BASE    = "https://api.trademe.co.nz/v1/"

# ------------------------------------------------------------------------------
# OAuth Credentials (set in environment or Replit secrets)
# ------------------------------------------------------------------------------
CONSUMER_KEY       = os.getenv("TRADEME_CONSUMER_KEY")
CONSUMER_SECRET    = os.getenv("TRADEME_CONSUMER_SECRET")
OAUTH_TOKEN        = os.getenv("TRADEME_OAUTH_TOKEN")
OAUTH_TOKEN_SECRET = os.getenv("TRADEME_OAUTH_TOKEN_SECRET")

if not all([CONSUMER_KEY, CONSUMER_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET]):
    raise RuntimeError(
        "Missing Trade Me credentials. Please set TRADEME_CONSUMER_KEY, "
        "TRADEME_CONSUMER_SECRET, TRADEME_OAUTH_TOKEN, and TRADEME_OAUTH_TOKEN_SECRET."
    )

# ------------------------------------------------------------------------------
# Metadata configuration
# ------------------------------------------------------------------------------
# Where to cache metadata JSON files
METADATA_DIR = Path(__file__).parents[1] / "metadata"
METADATA_DIR.mkdir(exist_ok=True)

# Endpoints for metadata
_METADATA_ENDPOINTS = {
    "Region":     "Locations/Region.json",
    "District":   "Locations/District.json",
    "Suburb":     "Locations/Suburb.json",
    "Attributes": "Categories/Property/Attributes.json",
}

# ------------------------------------------------------------------------------
# OAuth1 Session Factory
# ------------------------------------------------------------------------------

def get_client() -> OAuth1Session:
    """
    Create and return an OAuth1Session for authenticated Trade Me API calls.
    """
    return OAuth1Session(
        client_key=CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=OAUTH_TOKEN,
        resource_owner_secret=OAUTH_TOKEN_SECRET
    )

# ------------------------------------------------------------------------------
# Metadata Fetching & Loading
# ------------------------------------------------------------------------------

def fetch_metadata(sandbox: bool = True, refresh: bool = False) -> None:
    """
    Fetch and cache all metadata endpoints defined in `_METADATA_ENDPOINTS`.

    Args:
        sandbox: If True, uses the sandbox environment; otherwise, production.
        refresh: If True, re-fetch even if cache files exist.

    Side effects:
        Writes JSON files under data_gathering/metadata/{Name}.json
    """
    base = SANDBOX_BASE if sandbox else PROD_BASE
    client = get_client()
    for name, path in _METADATA_ENDPOINTS.items():
        out_path = METADATA_DIR / f"{name}.json"
        if out_path.exists() and not refresh:
            continue  # skip already-cached
        url = urljoin(base, path)
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_metadata(name: str) -> Dict[str, Any]:
    """
    Load a cached metadata file into a Python dict.

    Args:
        name: One of the keys in `_METADATA_ENDPOINTS` (e.g., "Region", "Suburb").

    Returns:
        Parsed JSON object from metadata/{name}.json.

    Raises:
        FileNotFoundError: if the metadata file is missing.
    """
    file_path = METADATA_DIR / f"{name}.json"
    if not file_path.exists():
        raise FileNotFoundError(
            f"Metadata '{name}' not found. Call fetch_metadata() first."
        )
    return json.loads(file_path.read_text(encoding="utf-8"))

# ------------------------------------------------------------------------------
# Property Search
# ------------------------------------------------------------------------------

def search_properties(
    section: str = "Residential",
    params: Dict[str, Any] = None,
    sandbox: bool = True
) -> Dict[str, Any]:
    """
    Search Trade Me Property listings.

    Args:
        section:  
          One of 'Residential', 'Rental', 'OpenHomes', etc.  
        params:  
          Dict of URL parameters (e.g., price_min, bedrooms_min, suburb).  
        sandbox:  
          If True, uses the sandbox environment; otherwise, production.

    Returns:
        Dict: Parsed JSON response with keys like 'List', 'TotalCount', etc.

    Raises:
        HTTPError: on API errors.
    """
    base = SANDBOX_BASE if sandbox else PROD_BASE
    endpoint = f"Search/Property/{section}.json"
    url = urljoin(base, endpoint)

    client = get_client()
    resp = client.get(url, params=params or {})
    resp.raise_for_status()
    return resp.json()
