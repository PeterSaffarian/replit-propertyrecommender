#!/usr/bin/env python3
"""
property_recommender/data_gathering/features/fetch_executor/fetch_executor.py

FetchExecutor fetches raw property listings from the Trade Me Property API,
based on search parameters produced by the QueryBuilder.

Responsibilities:
  1. Invoke the Trade Me API (via trademe_api.search_properties).
  2. Return the full JSON response for downstream normalization.
  3. (Optionally) save the raw JSON to disk for inspection or caching.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from property_recommender.data_gathering.providers.trademe_api import search_properties


class FetchExecutor:
    """
    FetchExecutor for retrieving raw property data from Trade Me.

    Workflow:
      - Initialize with environment (sandbox vs production).
      - fetch(): call search_properties() and return the JSON.
    """

    def __init__(
        self,
        sandbox: bool = True,
    ):
        """
        Initialize the FetchExecutor.

        Args:
            sandbox: If True, use the Trade Me sandbox endpoints; otherwise, production.
        """
        self.sandbox = sandbox

    def fetch(
        self,
        search_params: Dict[str, Any],
        section: str = "Residential",
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Execute a property search and retrieve raw listings.

        Args:
            search_params:  
                Dict of query parameters (e.g., price_min, bedrooms_min, suburb).
            section:  
                One of 'Residential', 'Rental', 'OpenHomes', etc.
            save_path:  
                Optional Path to write the raw JSON response (for caching or debugging).

        Returns:
            Dict[str, Any]: The parsed JSON response, including keys like 'List',
                            'TotalCount', 'Page', etc.

        Raises:
            HTTPError: If the API call fails (status 4xx or 5xx).
        """
        # 1. Call Trade Me API via our provider module
        response = search_properties(
            section=section,
            params=search_params,
            sandbox=self.sandbox
        )

        # 2. Optionally save the raw response to disk
        if save_path:
            try:
                save_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
            except Exception as e:
                # Non-fatal: log and continue
                print(f"Warning: failed to write raw data to {save_path}: {e}")

        # 3. Return for normalization
        return response


# Example standalone usage
if __name__ == "__main__":
    # Example: fetch 10 residential listings in suburb 2000
    executor = FetchExecutor(sandbox=True)
    params = {"suburb": 2000, "rows": 10}
    raw = executor.fetch(params, section="Residential", save_path=Path("raw_properties.json"))
    print(json.dumps(raw, indent=2))
