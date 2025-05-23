"""
property_recommender/data_gathering/features/query_builder/query_builder.py

This module maps a structured search request form (from the LLM) to Trade Me API parameters,
builds the search endpoint URL, and prepares an authenticated session.

Key functions:
  - build_params_from_form(form: dict) -> dict
  - build_search_query(form: dict) -> (endpoint: str, params: dict, session: OAuth1Session)

Raises:
  - ValueError on unmappable form values.

Usage:
  from data_gathering.features.query_builder.query_builder import build_search_query
  endpoint, params, session = build_search_query(form)
  response = session.get(endpoint, params=params)
"""
import logging
from typing import Tuple, Union
from requests_oauthlib import OAuth1Session

from property_recommender.data_gathering.providers.trademe_api import (
    BASE_URL,
    get_oauth_session,
    get_suburbs,
    get_regions,
    get_property_types,
    get_sales_methods,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Fixed endpoint for residential property search
SEARCH_PATH = "/Search/Property/Residential.json"


def build_params_from_form(form: dict) -> dict:
    """
    Convert the LLM form into Trade Me API query parameters.

    Args:
        form: Dict matching search_request_form.json schema.
    Returns:
        params: Dict of query parameters for Trade Me.

    Raises:
        ValueError: If a form value cannot be mapped to metadata.
    """
    params = {}
    # Location mapping
    loc = form.get("location", {})
    if "suburb" in loc:
        name = loc["suburb"]
        suburbs = get_suburbs()
        match = next((s for s in suburbs if s.get("Name", "").lower() == name.lower()), None)
        if not match:
            raise ValueError(f"Unknown suburb: {name}")
        params["suburb"] = match["SuburbId"]
    elif "city" in loc:
        # Treat city as region
        name = loc["city"]
        regions = get_regions()
        match = next((r for r in regions if r.get("Name", "").lower() == name.lower()), None)
        if not match:
            raise ValueError(f"Unknown city/region: {name}")
        params["region"] = match["RegionId"]
    elif "region" in loc:
        name = loc["region"]
        regions = get_regions()
        match = next((r for r in regions if r.get("Name", "").lower() == name.lower()), None)
        if not match:
            raise ValueError(f"Unknown region: {name}")
        params["region"] = match["RegionId"]

    if loc.get("nearby_suburbs"):
        params["adjacent_suburbs"] = True

    # Numeric ranges
    for key, pmin, pmax in [
        ("price_range", "price_min", "price_max"),
        ("bedroom_range", "bedrooms_min", "bedrooms_max"),
        ("bathroom_range", "bathrooms_min", "bathrooms_max"),
        ("parking_range", "car_spaces_min", "car_spaces_max"),
    ]:
        rng = form.get(key)
        if isinstance(rng, dict):
            if rng.get("min") is not None:
                params[pmin] = rng["min"]
            if rng.get("max") is not None:
                params[pmax] = rng["max"]

    # Property type(s)
    ptype = form.get("property_type")
    if ptype:
        # Accept string or list
        if isinstance(ptype, list):
            vals = ptype
        else:
            vals = [ptype]
        # Validate against metadata
        valid = get_property_types()
        choices = {item.get("Key", item.get("Value", "")): item for item in valid}
        selected = []
        for v in vals:
            if v in choices:
                selected.append(v)
            else:
                # try case-insensitive
                match = next((k for k in choices if k.lower() == v.lower()), None)
                if match:
                    selected.append(match)
                else:
                    raise ValueError(f"Unknown property_type: {v}")
        params["property_type"] = ",".join(selected)

    # Sales method
    sm = form.get("sales_method")
    if sm:
        methods = get_sales_methods()
        valid = {item.get("Key", item.get("Value", "")): item for item in methods}
        if sm in valid:
            params["sales_method"] = sm
        else:
            match = next((k for k in valid if k.lower() == sm.lower()), None)
            if match:
                params["sales_method"] = match
            else:
                raise ValueError(f"Unknown sales_method: {sm}")

    logger.info(f"Built query parameters: {params}")
    return params


def build_search_query(form: dict) -> Tuple[str, dict, Union[OAuth1Session, None]]:
    """
    Build the full search endpoint, parameters, and authenticated session.

    Args:
        form: Dict matching search_request_form.json schema.
    Returns:
        endpoint (str), params (dict), session (OAuth1Session).
    """
    session = get_oauth_session()
    endpoint = f"{BASE_URL}{SEARCH_PATH}"
    params = build_params_from_form(form)
    return endpoint, params, session

# End of query_builder.py