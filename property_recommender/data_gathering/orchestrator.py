"""
property_recommender/data_gathering/orchestrator.py

Top-level orchestrator for the property-recommender pipeline:
  1. Loads user_profile.json and environment settings.
  2. Runs the LLM-based user agent to generate a search request form.
  3. Builds Trade Me API query parameters and endpoint (with fallback to user profile).
  4. Uses fuzzy matching plus LLM confirmation for location mapping.
  5. Executes the search with pagination, rate-limit back-off, and retries.
  6. Saves intermediate files and all fetched raw properties to raw_properties.json.

Usage:
  python orchestrator.py

Dependencies:
  - OpenAI API credentials (via OPENAI_API_KEY env var).
  - Trade Me API credentials (via TRADEME_CONSUMER_KEY/SECRET in .env).
"""
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
        match_hints: {
            'region': {'input', 'candidate', 'id'},
            'district': {...},
            'suburb': {...}
        }
        model: OpenAI model name
        temperature: LLM temperature
    Returns:
        {"approved": bool, "correction": {<field>: <value>, ...}} JSON-parsed
    """
    # Build a descriptive prompt
    desc = []
    for level in ("region", "district", "suburb"):
        hint = match_hints.get(level, {})
        desc.append(f"{level.title()}: user input={hint.get('input')!r}, candidate={hint.get('candidate')!r}")
    system_prompt = (
        "You are a metadata-mapping assistant. A user’s location preferences "
        "have been interpreted as follows:\n" + "\n".join(desc) +
        "\nPlease confirm whether this full mapping is correct."
    )
    user_prompt = (
        "Respond ONLY in JSON. If the mapping is correct, output {\"approved\": true}."
        "If not, output {\"approved\": false, \"correction\": {\"level\": \"PreferredName\"}}"
    )
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from confirmation LLM: {content}")


def main(
    profile_path=None,
    raw_output_path=None,
    model="gpt-4o",
    temperature=0.7,
    retries=2,
    sandbox=True,
):
    logger.info("Starting property-recommender orchestration...")

    # Resolve paths and project root
    project_root = Path(__file__).parent.parent.parent
    user_profile_path = Path(profile_path) if profile_path else project_root / "user_profile.json"

    # Load user profile
    try:
        user_profile = json.loads(user_profile_path.read_text())
    except Exception as e:
        logger.error(f"Failed to load user profile: {e}")
        return

    # Step 1: Run LLM-based User Agent
    try:
        form = run_user_agent(user_profile_path)
        # Persist the filled form
        filled_form_path = Path(__file__).parent / "filled_form.json"
        filled_form_path.write_text(json.dumps(form, indent=2))
        logger.info(f"Saved filled form to {filled_form_path}")
    except Exception as e:
        logger.error(f"User Agent failed: {e}")
        return

    # Fallback: ensure at least one location field
    if not any(form.get(k) for k in ("region", "district", "suburb")):
        fallback_loc = (
            user_profile.get("location") or
            user_profile.get("city") or
            user_profile.get("district") or
            user_profile.get("suburb")
        )
        if fallback_loc:
            form["district"] = fallback_loc
            logger.info(f"No location from LLM; falling back to district={fallback_loc}")
        else:
            logger.error(
                "No location provided by LLM or user profile; cannot build scoped query."
            )
            return

    # Step 2: Build search query and save
    try:
        endpoint, params, session, match_hints = build_search_query(form)
        query_path = Path(__file__).parent / "search_query.json"
        query_path.write_text(json.dumps({"endpoint": endpoint, "params": params}, indent=2))
        logger.info(f"Saved search query to {query_path}")
    except ValueError as e:
        logger.error(f"Query building failed: {e}")
        return

    # Step 3: Confirm mapping with LLM
    try:
        confirmation = confirm_location_mapping(match_hints, model, temperature)
        if not confirmation.get("approved"):
            corrections = confirmation.get("correction", {})
            for level, corrected in corrections.items():
                form[level] = corrected
            logger.info(f"Mapping corrections applied: {corrections}")
            # Rebuild query after corrections
            endpoint, params, session, match_hints = build_search_query(form)
            query_path.write_text(json.dumps({"endpoint": endpoint, "params": params}, indent=2))
            logger.info(f"Saved corrected search query to {query_path}")
        else:
            logger.info("Location mapping approved by LLM.")
    except Exception as e:
        logger.error(f"Location confirmation failed: {e}")

    # Step 4: Execute fetch
    try:
        raw_properties = fetch_raw_properties(endpoint, params, session)
    except Exception as e:
        logger.error(f"Fetching properties failed: {e}")
        return

    # Step 5: Save final raw data
    output_path = Path(raw_output_path) if raw_output_path else project_root.parent / "raw_properties.json"
    output_path.write_text(json.dumps(raw_properties, indent=2))
    logger.info(f"Saved {len(raw_properties)} properties to {output_path}")


if __name__ == "__main__":
    main()
