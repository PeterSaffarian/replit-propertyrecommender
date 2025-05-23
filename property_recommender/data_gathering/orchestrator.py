"""
property_recommender/data_gathering/orchestrator.py

Top-level orchestrator for the property-recommender pipeline:
  1. Loads user_profile.json and environment settings.
  2. Runs the LLM-based user agent to generate a search request form.
  3. Builds Trade Me API query parameters and endpoint.
  4. Executes the search with pagination, rate-limit back-off, and retries.
  5. Saves all fetched raw properties to raw_properties.json at project root.

Usage:
  python orchestrator.py

Dependencies:
  - OpenAI API credentials (via OPENAI_API_KEY env var).
  - Trade Me API credentials (via TRADEME_CONSUMER_KEY/SECRET in .env).

"""
import json
import logging
from pathlib import Path

from data_gathering.features.user_agent.user_agent import run_user_agent
from data_gathering.features.query_builder.query_builder import build_search_query
from data_gathering.features.fetch_executor.fetch_executor import fetch_raw_properties

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting property-recommender orchestration...")

    # Paths
    project_root = Path(__file__).parent.parent
    user_profile_path = project_root / "user_profile.json"

    # Step 1: User Agent (LLM)
    try:
        form = run_user_agent(user_profile_path)
    except Exception as e:
        logger.error(f"User Agent failed: {e}")
        return

    # Step 2: Build query parameters
    try:
        endpoint, params, session = build_search_query(form)
    except ValueError as e:
        logger.error(f"Query building failed: {e}")
        return

    # Step 3: Execute fetch
    try:
        raw_properties = fetch_raw_properties(endpoint, params, session)
    except Exception as e:
        logger.error(f"Fetching properties failed: {e}")
        return

    # Step 4: Save results
    output_path = project_root.parent / "raw_properties.json"
    output_path.write_text(json.dumps(raw_properties, indent=2))
    logger.info(f"Saved {len(raw_properties)} properties to {output_path}")


if __name__ == "__main__":
    main()
