"""
property_recommender/data_gathering/features/user_agent/user_agent.py

This module runs the LLM-based "User Agent" to translate a raw user profile
into a structured search request form. It:
  1. Loads the user profile JSON.
  2. Builds system/user messages via prompts.py.
  3. Calls the OpenAI ChatCompletion API.
  4. Parses and validates the returned JSON against the search_request_form schema.
  5. Raises an error if validation fails, allowing orchestration logic to request refinement.

Functions:
  - run_user_agent(user_profile_path: Path) -> dict

Usage:
  from data_gathering.features.user_agent.user_agent import run_user_agent
  form = run_user_agent(Path("user_profile.json"))
"""
import json
import logging
from pathlib import Path

from openai import OpenAI

client = OpenAI()
from jsonschema import validate, ValidationError

from .prompts import build_user_agent_messages, SEARCH_SCHEMA

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def run_user_agent(user_profile_path: Path, model: str = "gpt-4o") -> dict:
    """
    Execute the LLM user-agent to generate a search request form.

    Args:
        user_profile_path: Path to the user_profile.json file.
        model: OpenAI model to use (default: gpt-4o).

    Returns:
        A dict matching the SEARCH_SCHEMA.

    Raises:
        ValueError: If the LLM response is invalid JSON or fails schema validation.
        openai.error.OpenAIError: If the API call fails.
    """
    # Load user profile
    try:
        user_profile = json.loads(Path("user_profile.json").read_text())
    except Exception as e:
        logger.error(f"Failed to load user profile: {e}")
        raise

    # Build messages for ChatCompletion
    messages = build_user_agent_messages(json.dumps(user_profile, indent=2))

    # Call the OpenAI API
    logger.info("Calling LLM for user-agent form generation...")
    response = client.chat.completions.create(model=model,
    messages=messages,
    temperature=0)
    content = response.choices[0].message.content

    # Parse JSON
    try:
        form = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}\nContent: {content}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # Validate against schema
    try:
        validate(instance=form, schema=SEARCH_SCHEMA)
    except ValidationError as e:
        logger.error(f"Schema validation error: {e.message}")
        raise ValueError(f"Search form failed validation: {e.message}") from e

    logger.info("User-agent form generated and validated successfully.")
    return form


if __name__ == "__main__":
    # Example execution
    path = Path(__file__).parent.parent.parent.parent / "user_profile.json"
    form = run_user_agent(path)
    print(json.dumps(form, indent=2))
