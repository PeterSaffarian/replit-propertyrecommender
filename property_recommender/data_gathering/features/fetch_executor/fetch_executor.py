"""
property_recommender/data_gathering/features/fetch_executor/fetch_executor.py

This module handles executing Trade Me property search requests:
  1. Executes the search endpoint via OAuth session.
  2. Handles pagination, rate-limit back-off, and retries.
  3. Logs progress with timestamps and counts.
  4. Returns a list of raw property JSON objects.

Functions:
  - fetch_raw_properties(endpoint: str, params: dict, session, max_pages: int = None) -> list

Usage:
  from data_gathering.features.fetch_executor.fetch_executor import fetch_raw_properties
  raw_props = fetch_raw_properties(endpoint, params, session)

"""
import time
import logging
from typing import List, Dict, Any, Optional

# Configure logging with timestamp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Raised when fetching fails after retries."""
    pass


def fetch_raw_properties(
    endpoint: str,
    params: Dict[str, Any],
    session,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all pages of search results from Trade Me.

    Args:
        endpoint: Full API URL for the search endpoint.
        params: Query parameters (excluding 'page').
        session: Authenticated OAuth1 session.
        max_pages: Optional cap on number of pages to fetch.

    Returns:
        List of raw property items (dicts).

    Raises:
        FetchError: If repeated retries fail for a page.
    """
    all_items: List[Dict[str, Any]] = []
    page = 1

    while True:
        # Prepare params for this page
        req_params = params.copy()
        req_params['page'] = page

        retries = 0
        while True:
            try:
                logger.info(f"Fetching page {page}...")
                response = session.get(endpoint, params=req_params)
                if response.status_code == 429:
                    # Rate limited
                    wait = 60  # seconds
                    logger.warning(f"Rate limited on page {page}. Backing off for {wait}s.")
                    time.sleep(wait)
                    retries += 1
                elif response.status_code >= 500:
                    # Server error
                    wait = 5 * (retries + 1)
                    logger.warning(f"Server error ({response.status_code}) on page {page}. Retrying in {wait}s.")
                    time.sleep(wait)
                    retries += 1
                else:
                    response.raise_for_status()
                    break
                if retries >= 3:
                    raise FetchError(f"Failed to fetch page {page} after {retries} retries.")
            except Exception as e:
                if retries >= 3:
                    logger.error(f"Error fetching page {page}: {e}")
                    raise FetchError(f"Error fetching page {page}: {e}") from e
                # else, retry

        data = response.json()
        items = data.get('List', [])
        count = len(items)
        logger.info(f"Page {page} fetched: {count} items.")

        all_items.extend(items)

        # Pagination logic
        total = data.get('TotalCount')
        page_size = data.get('PageSize')
        fetched = page * page_size

        if count == 0:
            logger.info(f"No items on page {page}, ending fetch.")
            break
        if max_pages and page >= max_pages:
            logger.info(f"Reached max_pages={max_pages}, ending fetch.")
            break
        if fetched >= total:
            logger.info(f"Fetched all {total} items across {page} pages.")
            break

        page += 1

    logger.info(f"Total properties fetched: {len(all_items)}")
    return all_items


if __name__ == '__main__':
    # Example usage (requires real endpoint, params, and session):
    from data_gathering.features.query_builder.query_builder import build_search_query
    from data_gathering.providers.trademe_api import get_oauth_session

    # Dummy form for example
    form = {}
    endpoint, params, session = build_search_query(form)
    props = fetch_raw_properties(endpoint, params, session, max_pages=2)
    print(f"Fetched {len(props)} properties")
