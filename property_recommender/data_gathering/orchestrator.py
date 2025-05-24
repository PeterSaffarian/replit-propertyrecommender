"""
property_recommender/data_gathering/orchestrator.py

Top-level orchestrator for the property-recommender pipeline:
  1. Loads user_profile.json and environment settings.
  2. Runs the LLM-based user agent to generate a search request form.
  3. Builds Trade Me API query parameters and endpoint.
  4. Uses the LLM to validate (and correct) the query, with configurable retries.
  5. Executes the search with pagination, rate-limit back-off, and retries.
  6. Saves intermediate files and all fetched raw properties to raw_properties.json.

Usage:
  python -m property_recommender.data_gathering.orchestrator
"""

import argparse
import json
import logging
from pathlib import Path

from property_recommender.data_gathering.features.user_agent.user_agent import run_user_agent, user_agent
from property_recommender.data_gathering.features.query_builder.query_builder import build_search_query
from property_recommender.data_gathering.features.fetch_executor.fetch_executor import fetch_raw_properties

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# How many times to ask the LLM to fix missing fields
MAX_VALIDATION_TRIES = 2


def main():
    parser = argparse.ArgumentParser(description="Run the property-recommender orchestrator.")
    parser.add_argument("--profile",     help="Path to user_profile.json")
    parser.add_argument("--output",      help="Path to save raw_properties.json")
    parser.add_argument("--model",       default="gpt-4o", help="OpenAI model to use")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature")
    parser.add_argument("--max-pages",   type=int, default=1, help="Maximum pages to fetch (default: 1 for testing)")
    args = parser.parse_args()

    logger.info("Starting property-recommender orchestration...")
    project_root = Path(__file__).parent.parent.parent
    profile_path = Path(args.profile) if args.profile else project_root / "user_profile.json"

    # Load user profile
    try:
        user_profile = json.loads(profile_path.read_text())
    except Exception as e:
        logger.error(f"Failed to load user profile: {e}")
        return

    # Step 1: User Agent → filled_form.json
    try:
        form = run_user_agent(profile_path)
        filled_path = Path(__file__).parent / "filled_form.json"
        filled_path.write_text(json.dumps(form, indent=2))
        logger.info(f"Saved filled form to {filled_path}")
    except Exception as e:
        logger.error(f"User Agent failed: {e}")
        return

    # Fallback: ensure at least a district if LLM omitted all location
    if not any(form.get(k) for k in ("region", "district", "suburb")):
        fb = user_profile.get("location") or user_profile.get("city") or user_profile.get("suburb")
        if fb:
            form["district"] = fb
            logger.info(f"No location from LLM; falling back to district={fb}")
        else:
            logger.error("No location provided; aborting.")
            return

    # Step 2: Build + validate search query with LLM corrections
    endpoint = params = session = None
    for attempt in range(1, MAX_VALIDATION_TRIES + 1):
        try:
            endpoint, params, session, match_hints = build_search_query(form)
            # save the candidate query each attempt
            query_path = Path(__file__).parent / "search_query.json"
            query_path.write_text(json.dumps({"endpoint": endpoint, "params": params}, indent=2))
            logger.info(f"Attempt {attempt}: Built search query, saved to {query_path}")

            verdict = user_agent.validate_search_query(
                form=form,
                query={"endpoint": endpoint, "params": params},
                match_hints=match_hints
            )

            if verdict.get("approved"):
                logger.info(f"Search query approved on attempt {attempt}.")
                break

            suggestions = verdict.get("suggestions", {})
            if suggestions:
                form.update(suggestions)
                logger.info(f"Applied LLM suggestions on attempt {attempt}: {suggestions}")
            else:
                logger.warning(f"Attempt {attempt}: No suggestions provided; proceeding with current query.")
                break

        except Exception as e:
            logger.error(f"Attempt {attempt}: Query validation failed: {e}")
    else:
        logger.warning(
            f"Query not approved after {MAX_VALIDATION_TRIES} attempts; proceeding with last built query."
        )

    # Step 3: Fetch raw properties
    try:
        raw_props = fetch_raw_properties(endpoint, params, session, max_pages=args.max_pages)
        logger.info(f"Limited fetch to {args.max_pages} page(s) for faster testing")
    except Exception as e:
        logger.error(f"Fetching properties failed: {e}")
        return

    # Step 4: Save raw data
    out_path = Path(args.output) if args.output else project_root / "raw_properties.json"
    out_path.write_text(json.dumps(raw_props, indent=2))
    logger.info(f"Saved {len(raw_props)} properties to {out_path}")


if __name__ == "__main__":
    main()
