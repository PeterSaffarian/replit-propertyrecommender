"""
property_recommender/data_gathering/features/fetch_executor/fetch_executor.py

This module handles executing Trade Me property search requests and fetching full listing details:
  1. Executes the search endpoint via OAuth session to get listing summaries.
  2. For each ListingId, fetches complete listing details from the Listing Details endpoint.
  3. Handles pagination, rate-limit back-off, and retries.
  4. Logs progress with timestamps and counts.
  5. Returns a list of complete raw property JSON objects (no processing).

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


def fetch_listing_details(session, listing_id: int, retries: int = 0) -> Optional[Dict[str, Any]]:
    """
    Fetch complete listing details for a single property.
    
    Args:
        session: Authenticated OAuth1 session.
        listing_id: The Trade Me listing ID.
        retries: Current retry count.
    
    Returns:
        Complete listing data as dict, or None if failed.
    """
    # Determine the base URL based on environment
    import os
    env = os.getenv("TM_ENV", "sandbox")
    if env == "production":
        base_url = "https://api.trademe.co.nz"
    else:
        base_url = "https://api.tmsandbox.co.nz"
    
    details_url = f"{base_url}/v1/Listings/{listing_id}.json"
    
    try:
        logger.info(f"Fetching details for listing {listing_id}...")
        response = session.get(details_url)
        
        if response.status_code == 429:
            # Rate limited
            wait = 60
            logger.warning(f"Rate limited for listing {listing_id}. Backing off for {wait}s.")
            time.sleep(wait)
            if retries < 3:
                return fetch_listing_details(session, listing_id, retries + 1)
            else:
                logger.error(f"Failed to fetch listing {listing_id} after rate limit retries.")
                return None
                
        elif response.status_code >= 500:
            # Server error
            wait = 5 * (retries + 1)
            logger.warning(f"Server error ({response.status_code}) for listing {listing_id}. Retrying in {wait}s.")
            time.sleep(wait)
            if retries < 3:
                return fetch_listing_details(session, listing_id, retries + 1)
            else:
                logger.error(f"Failed to fetch listing {listing_id} after server error retries.")
                return None
        else:
            response.raise_for_status()
            return response.json()
            
    except Exception as e:
        if retries < 3:
            logger.warning(f"Error fetching listing {listing_id}: {e}. Retrying...")
            time.sleep(2)
            return fetch_listing_details(session, listing_id, retries + 1)
        else:
            logger.error(f"Failed to fetch listing {listing_id} after {retries} retries: {e}")
            return None


def fetch_raw_properties(
    endpoint: str,
    params: Dict[str, Any],
    session,
    max_pages: Optional[int] = None,
    max_records: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch complete property listing details from Trade Me.
    
    First gets search results to obtain ListingId values, then fetches 
    complete listing details for each property.

    Args:
        endpoint: Full API URL for the search endpoint.
        params: Query parameters (excluding 'page').
        session: Authenticated OAuth1 session.
        max_pages: Optional cap on number of pages to fetch.
        max_records: Optional cap on total number of records to fetch.

    Returns:
        List of complete raw property listing objects (no processing).

    Raises:
        FetchError: If repeated retries fail for a page.
    """
    # Step 1: Get all listing IDs from search results
    all_listing_ids: List[int] = []
    page = 1

    while True:
        # Prepare params for this page
        req_params = params.copy()
        req_params['page'] = page

        retries = 0
        while True:
            try:
                logger.info(f"Fetching search page {page}...")
                response = session.get(endpoint, params=req_params)
                if response.status_code == 429:
                    # Rate limited
                    wait = 60  # seconds
                    logger.warning(f"Rate limited on search page {page}. Backing off for {wait}s.")
                    time.sleep(wait)
                    retries += 1
                elif response.status_code >= 500:
                    # Server error
                    wait = 5 * (retries + 1)
                    logger.warning(f"Server error ({response.status_code}) on search page {page}. Retrying in {wait}s.")
                    time.sleep(wait)
                    retries += 1
                else:
                    response.raise_for_status()
                    break
                if retries >= 3:
                    raise FetchError(f"Failed to fetch search page {page} after {retries} retries.")
            except Exception as e:
                if retries >= 3:
                    logger.error(f"Error fetching search page {page}: {e}")
                    raise FetchError(f"Error fetching search page {page}: {e}") from e
                # else, retry

        data = response.json()
        items = data.get('List', [])
        count = len(items)
        logger.info(f"Search page {page} fetched: {count} items.")

        # Extract ListingId from each item
        page_listing_ids = []
        for item in items:
            listing_id = item.get('ListingId')
            if listing_id:
                page_listing_ids.append(listing_id)
        
        all_listing_ids.extend(page_listing_ids)
        logger.info(f"Collected {len(page_listing_ids)} listing IDs from page {page}")

        # Pagination logic
        total = data.get('TotalCount')
        page_size = data.get('PageSize')
        fetched = page * page_size

        if count == 0:
            logger.info(f"No items on search page {page}, ending search fetch.")
            break
        if max_pages and page >= max_pages:
            logger.info(f"Reached max_pages={max_pages}, ending search fetch.")
            break
        if max_records and len(all_listing_ids) >= max_records:
            logger.info(f"Reached max_records={max_records}, ending search fetch.")
            break
        if fetched >= total:
            logger.info(f"Fetched all {total} search items across {page} pages.")
            break

        page += 1

    logger.info(f"Total listing IDs collected: {len(all_listing_ids)}")

    # Apply max_records limit to listing IDs if specified
    if max_records and len(all_listing_ids) > max_records:
        all_listing_ids = all_listing_ids[:max_records]
        logger.info(f"Trimmed listing IDs to max_records={max_records}")

    # Step 2: Fetch complete details for each listing
    complete_listings: List[Dict[str, Any]] = []
    
    for i, listing_id in enumerate(all_listing_ids, 1):
        logger.info(f"Fetching details {i}/{len(all_listing_ids)} for listing {listing_id}")
        
        details = fetch_listing_details(session, listing_id)
        if details:
            complete_listings.append(details)
            logger.info(f"Successfully fetched details for listing {listing_id}")
        else:
            logger.warning(f"Failed to fetch details for listing {listing_id}")
        
        # Small delay between requests to be respectful to the API
        time.sleep(0.5)

    logger.info(f"Total complete listings fetched: {len(complete_listings)}")
    return complete_listings


if __name__ == '__main__':
    # Example usage (requires real endpoint, params, and session):
    from data_gathering.features.query_builder.query_builder import build_search_query
    from data_gathering.providers.trademe_api import get_oauth_session

    # Dummy form for example
    form = {}
    endpoint, params, session = build_search_query(form)
    props = fetch_raw_properties(endpoint, params, session, max_pages=2)
    print(f"Fetched {len(props)} properties")
