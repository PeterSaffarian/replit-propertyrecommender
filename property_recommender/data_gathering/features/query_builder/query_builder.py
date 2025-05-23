"""
property_recommender/data_gathering/features/query_builder/query_builder.py

This module maps a structured search request form (from the LLM) to Trade Me API parameters,
builds the search endpoint URL, and prepares an authenticated session, with enhanced fuzzy matching
and metadata-mapping hints for LLM confirmation.

Key functions:
  - build_params_from_form(form: dict) -> (params: dict, match_hints: dict)
  - build_search_query(form: dict) -> (endpoint: str, params: dict, session: OAuth1Session, match_hints: dict)

Raises:
  - ValueError on unmappable form values.
"""

import logging
import difflib
from typing import Tuple, Union, Dict, Any

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


def fuzzy_match_item(name: str, items: list, name_key: str) -> Any:
    """
    Fuzzy-match a name against a list of items using:
      1) exact match
      2) substring match
      3) close match via difflib
    Returns the first matching item or None.
    """
    target = name.lower().strip()
    # 1) Exact match
    for item in items:
        candidate = item.get(name_key, "")
        if isinstance(candidate, str) and candidate.lower() == target:
            return item
    # 2) Substring match
    for item in items:
        candidate = item.get(name_key, "").lower()
        if target in candidate or candidate in target:
            return item
    # 3) Fuzzy match
    names = [item.get(name_key, "") for item in items if isinstance(item.get(name_key), str)]
    close = difflib.get_close_matches(target, names, n=1, cutoff=0.6)
    if close:
        for item in items:
            if item.get(name_key) == close[0]:
                return item
    return None


def build_params_from_form(form: dict) -> Tuple[dict, dict]:
    """
    Convert the LLM form into Trade Me API query parameters and produce match hints.

    Returns:
        params (dict): Query parameters for Trade Me.
        match_hints (dict): Mapping details for region, district, and suburb.

    Raises:
        ValueError: If a form value cannot be matched or mapped.
    """
    params: Dict[str, Any] = {}
    match_hints: Dict[str, Dict[str, Any]] = {
        "region":   {"input": form.get("region"),   "candidate": None, "id": None},
        "district": {"input": form.get("district"), "candidate": None, "id": None},
        "suburb":   {"input": form.get("suburb"),   "candidate": None, "id": None},
    }

    form_region = form.get("region")
    form_district = form.get("district")
    form_suburb = form.get("suburb")

    regions = get_regions()
    region_obj = None
    district_obj = None
    suburb_obj = None

    # 1) If district provided, match district first
    if form_district:
        for r in regions:
            d = fuzzy_match_item(form_district, r.get("Districts", []), "Name")
            if d:
                region_obj = r
                district_obj = d
                break

    # 2) If suburb provided within matched district
    if form_suburb and district_obj:
        s = fuzzy_match_item(form_suburb, district_obj.get("Suburbs", []), "Name")
        if s:
            suburb_obj = s

    # 3) Global suburb fallback if no district or no suburb match
    if form_suburb and not suburb_obj:
        for r in regions:
            for d in r.get("Districts", []):
                s = fuzzy_match_item(form_suburb, d.get("Suburbs", []), "Name")
                if s:
                    region_obj = r
                    district_obj = d
                    suburb_obj = s
                    break
            if suburb_obj:
                break

    # 4) Region match if still missing
    if not (region_obj or district_obj or suburb_obj) and form_region:
        r = fuzzy_match_item(form_region, regions, "Name")
        if r:
            region_obj = r

    # 5) Propagate region or district from deeper matches
    if suburb_obj and not district_obj:
        for r in regions:
            for d in r.get("Districts", []):
                if any(s.get("SuburbId") == suburb_obj.get("SuburbId") for s in d.get("Suburbs", [])):
                    district_obj = d
                    region_obj = r
                    break
            if district_obj:
                break

    if district_obj and not region_obj:
        for r in regions:
            if any(d.get("DistrictId") == district_obj.get("DistrictId") for d in r.get("Districts", [])):
                region_obj = r
                break

    # Populate match_hints
    if region_obj:
        match_hints["region"]["candidate"] = region_obj.get("Name")
        match_hints["region"]["id"] = region_obj.get("LocalityId")
    if district_obj:
        match_hints["district"]["candidate"] = district_obj.get("Name")
        match_hints["district"]["id"] = district_obj.get("DistrictId")
    if suburb_obj:
        match_hints["suburb"]["candidate"] = suburb_obj.get("Name")
        match_hints["suburb"]["id"] = suburb_obj.get("SuburbId")

    # Populate params based on best match
    if suburb_obj:
        params["suburb"] = suburb_obj.get("SuburbId")
    elif district_obj:
        params["district"] = district_obj.get("DistrictId")
    elif region_obj:
        params["region"] = region_obj.get("LocalityId")

    # Numeric ranges
    numeric_map = [
        ("min_price", "price_min"), ("max_price", "price_max"),
        ("min_bedrooms", "bedrooms_min"), ("max_bedrooms", "bedrooms_max"),
        ("min_bathrooms", "bathrooms_min"), ("max_bathrooms", "bathrooms_max"),
        ("min_carparks", "car_spaces_min"), ("max_carparks", "car_spaces_max"),
    ]
    for form_key, param_key in numeric_map:
        if form.get(form_key) is not None:
            params[param_key] = form.get(form_key)

    # Property types
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
                m = next((k for k in choices if k.lower() == v.lower()), None)
                if m:
                    selected.append(m)
                else:
                    raise ValueError(f"Unknown property_type: {v}")
        params["property_type"] = ",".join(selected)

    # Sales methods
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
                m = next((k for k in choices if k.lower() == v.lower()), None)
                if m:
                    selected.append(m)
                else:
                    raise ValueError(f"Unknown sales_method: {v}")
        params["sales_method"] = ",".join(selected)

    logger.info(f"Built query parameters: {params}")
    return params, match_hints


def build_search_query(
    form: dict
) -> Tuple[str, dict, Union['OAuth1Session', None], dict]:
    """
    Build the full search endpoint, parameters, session, and mapping hints.

    Returns:
        endpoint (str), params (dict), session (OAuth1Session), match_hints (dict)
    """
    session = get_oauth_session()
    endpoint = f"{BASE_URL}{SEARCH_PATH}"
    params, match_hints = build_params_from_form(form)
    return endpoint, params, session, match_hints
