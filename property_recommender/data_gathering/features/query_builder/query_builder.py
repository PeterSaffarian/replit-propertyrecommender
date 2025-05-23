"""
property_recommender/data_gathering/features/query_builder/query_builder.py

This module maps a structured search request form (from the LLM) to Trade Me API parameters,
builds the search endpoint URL, and prepares an authenticated session.

Key functions:
  - build_params_from_form(form: dict) -> dict
  - build_search_query(form: dict) -> (endpoint: str, params: dict, session: OAuth1Session)

Raises:
  - ValueError on unmappable form values.
"""

import logging
from typing import Tuple, Union

from property_recommender.data_gathering.providers.trademe_api import (
    BASE_URL,
    get_oauth_session,
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

    # Extract location fields
    form_region = form.get("region")
    form_district = form.get("district")
    form_suburb = form.get("suburb")

    region_obj = None
    district_obj = None
    suburb_obj = None

    regions = get_regions()

    # 1) Try matching suburb first
    if form_suburb:
        for r in regions:
            for d in r.get("Districts", []):
                for s in d.get("Suburbs", []):
                    if s.get("Name", "").lower() == form_suburb.lower():
                        region_obj = r
                        district_obj = d
                        suburb_obj = s
                        break
                if suburb_obj:
                    break
            if suburb_obj:
                break

    # 2) Try matching district
    if not suburb_obj and form_district:
        for r in regions:
            for d in r.get("Districts", []):
                if d.get("Name", "").lower() == form_district.lower():
                    region_obj = r
                    district_obj = d
                    break
            if district_obj:
                break

    # 3) Try matching region
    if not region_obj and form_region:
        region_obj = next(
            (r for r in regions if r.get("Name", "").lower() == form_region.lower()),
            None
        )

    # 4) Fallback: region field may contain district or suburb
    if not region_obj and form_region:
        # District fallback
        for r in regions:
            for d in r.get("Districts", []):
                if d.get("Name", "").lower() == form_region.lower():
                    region_obj = r
                    district_obj = d
                    break
            if region_obj:
                break

    if not region_obj and form_region:
        # Suburb fallback
        for r in regions:
            for d in r.get("Districts", []):
                for s in d.get("Suburbs", []):
                    if s.get("Name", "").lower() == form_region.lower():
                        region_obj = r
                        district_obj = d
                        suburb_obj = s
                        break
                if suburb_obj:
                    break
            if suburb_obj:
                break

    # Populate region/district/suburb parameters
    if suburb_obj:
        params["suburb"] = suburb_obj.get("SuburbId")
    elif district_obj:
        params["district"] = district_obj.get("DistrictId")
    elif region_obj:
        params["region"] = region_obj.get("LocalityId")

    # Numeric ranges
    if form.get("min_price") is not None:
        params["price_min"] = form["min_price"]
    if form.get("max_price") is not None:
        params["price_max"] = form["max_price"]
    if form.get("min_bedrooms") is not None:
        params["bedrooms_min"] = form["min_bedrooms"]
    if form.get("max_bedrooms") is not None:
        params["bedrooms_max"] = form["max_bedrooms"]
    if form.get("min_bathrooms") is not None:
        params["bathrooms_min"] = form["min_bathrooms"]
    if form.get("max_bathrooms") is not None:
        params["bathrooms_max"] = form["max_bathrooms"]
    if form.get("min_carparks") is not None:
        params["car_spaces_min"] = form["min_carparks"]
    if form.get("max_carparks") is not None:
        params["car_spaces_max"] = form["max_carparks"]

    # Adjacent suburbs if suburb was specified
    if suburb_obj and form.get("adjacent_suburbs"):
        params["adjacent_suburbs"] = True

    # Property type(s)
    types = form.get("property_types")
    if types:
        vals = types if isinstance(types, list) else [types]
        valid = get_property_types()
        choices = {item.get("Key", item.get("Value", "")): item for item in valid}
        selected = []
        for v in vals:
            if v in choices:
                selected.append(v)
            else:
                match = next((k for k in choices if k.lower() == v.lower()), None)
                if match:
                    selected.append(match)
                else:
                    raise ValueError(f"Unknown property_type: {v}")
        params["property_type"] = ",".join(selected)

    # Sales method(s)
    methods = form.get("sales_methods")
    if methods:
        vals = methods if isinstance(methods, list) else [methods]
        valid = get_sales_methods()
        choices = {item.get("Key", item.get("Value", "")): item for item in valid}
        selected = []
        for v in vals:
            if v in choices:
                selected.append(v)
            else:
                match = next((k for k in choices if k.lower() == v.lower()), None)
                if match:
                    selected.append(match)
                else:
                    raise ValueError(f"Unknown sales_method: {v}")
        params["sales_method"] = ",".join(selected)

    logger.info(f"Built query parameters: {params}")
    return params


def build_search_query(form: dict) -> Tuple[str, dict, Union['OAuth1Session', None]]:
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
