"""
property_recommender/data_gathering/orchestrator.py

Top-level orchestrator for the property-recommender pipeline:
  1. Loads user_profile.json and environment settings.
  2. Runs the LLM-based user agent to generate a search request form.
  3. Builds Trade Me API query parameters and endpoint (with fallback to user profile).
  4. Uses fuzzy matching plus LLM confirmation for location mapping, with configurable retries.
  5. Executes the search with pagination, rate-limit back-off, and retries.
  6. Saves intermediate files and all fetched raw properties to raw_properties.json.

Usage:
  python -m property_recommender.data_gathering.orchestrator --retries=<n>

Dependencies:
  - OpenAI API credentials (via OPENAI_API_KEY env var).
  - Trade Me API credentials (via TRADEME_CONSUMER_KEY/SECRET in .env).
"""
import argparse
import json
import logging
from pathlib import Path

from openai import OpenAI
from property_recommender.data_gathering.features.user_agent.user_agent import run_user_agent
from property_recommender.data_gathering.features.query_builder.query_builder import build_search_query
from property_recommender.data_gathering.features.fetch_executor.fetch_executor import fetch_raw_properties

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def confirm_location_mapping(match_hints: dict, model: str, temperature: float) -> dict:
    """
    Ask the LLM to confirm or correct the inferred location mapping.

    Args:
        match_hints: dict with keys 'region','district','suburb', each containing:
                     {input: str, candidate: str|None, id: int|None}
        model: OpenAI model name
        temperature: LLM temperature
    Returns:
        dict {"approved": bool, "correction": {<level>: <value>, ...}}
    """
    # Build description
    desc_lines = []
    for level in ("region", "district", "suburb"):
        hint = match_hints.get(level, {})
        desc_lines.append(
            f"{level.title()}: user input={hint.get('input')!r}, candidate={hint.get('candidate')!r}"  
        )
    system_prompt = (
        "You are a metadata-mapping assistant. A user’s location has been interpreted as follows:"
        + ".join(desc_lines)"
        + "Please confirm whether each of these mappings is correct."
    )
    user_prompt = (
        "Respond ONLY in JSON."
        " If all mappings are correct, output {\"approved\": true}."
        " If any mapping is missing or incorrect, output {\"approved\": false, \"correction\": {<level>: <best guess>, ...}}", 
        # e.g.: {"approved": false, "correction": {"suburb": "Central City"}}
    )
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from confirmation LLM: {content}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from confirmation LLM: {content}")


def main():
    parser = argparse.ArgumentParser(description="Run the property-recommender orchestrator.")
    parser.add_argument("--profile",     help="Path to user_profile.json")
    parser.add_argument("--output",      help="Path to save raw_properties.json")
    parser.add_argument("--model",       default="gpt-4o", help="OpenAI model to use")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM temperature")
    parser.add_argument("--retries",     type=int,   default=2,   help="Number of confirmation retries")
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

    # Step 1: User Agent
    try:
        form = run_user_agent(profile_path)
        save_path = Path(__file__).parent / "filled_form.json"
        save_path.write_text(json.dumps(form, indent=2))
        logger.info(f"Saved filled form to {save_path}")
    except Exception as e:
        logger.error(f"User Agent failed: {e}")
        return

    # Fallback: ensure location
    if not any(form.get(k) for k in ("region","district","suburb")):
        fb = user_profile.get("location") or user_profile.get("city") or user_profile.get("suburb")
        if fb:
            form["district"] = fb
            logger.info(f"No location from LLM; falling back to district={fb}")
        else:
            logger.error("No location provided; aborting.")
            return

    # Step 2: Build initial query & hints
    try:
        endpoint, params, session, match_hints = build_search_query(form)
        save_path = Path(__file__).parent / "search_query.json"
        save_path.write_text(json.dumps({"endpoint": endpoint, "params": params}, indent=2))
        logger.info(f"Saved initial search query to {save_path}")
    except ValueError as e:
        logger.error(f"Query building failed: {e}")
        return

    # Step 3: Confirm mapping with retries
    for attempt in range(1, args.retries + 1):
        try:
            conf = confirm_location_mapping(match_hints, args.model, args.temperature)
        except Exception as e:
            logger.error(f"Confirmation attempt {attempt} failed: {e}")
            continue

        if conf.get("approved"):
            logger.info(f"Location mapping approved on attempt {attempt}.")
            break

        corrections = conf.get("correction", {})
        if corrections:
            form.update(corrections)
            logger.info(f"Applied corrections (attempt {attempt}): {corrections}")
            endpoint, params, session, match_hints = build_search_query(form)
            (project_root / "data_gathering" / "search_query.json").write_text(
                json.dumps({"endpoint": endpoint, "params": params}, indent=2)
            )
            logger.info("Saved corrected search query")
        else:
            logger.error(f"No corrections provided on attempt {attempt}; aborting confirmation.")
            break
    else:
        logger.warning(f"Mapping not approved after {args.retries} attempts, proceeding with last mapping.")

    # Step 4: Fetch
    try:
        raw_props = fetch_raw_properties(endpoint, params, session)
    except Exception as e:
        logger.error(f"Fetching properties failed: {e}")
        return

    # Step 5: Save raw data
    out_path = Path(args.output) if args.output else Path(__file__).parent.parent / "raw_properties.json"
    out_path.write_text(json.dumps(raw_props, indent=2))
    logger.info(f"Saved {len(raw_props)} properties to {out_path}")


if __name__ == "__main__":
    main()
