"""
property_recommender/data_gathering/features/user_agent/user_agent.py

This module runs the LLM-based "User Agent" to:
  1. Translate a raw user profile into a structured search request form.
  2. Validate (and, if needed, correct) a candidate search_query via an LLM check.

It exposes:
  - run_user_agent(user_profile_path: Path, model: str="gpt-4o") -> dict
  - user_agent.validate_search_query(form: dict, query: dict) -> dict
"""

import json
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from jsonschema import validate, ValidationError

from .prompts import (
    build_user_agent_messages,
    SEARCH_SCHEMA,
    VALIDATE_SEARCH_QUERY,
)

# module‐level OpenAI client
client = OpenAI()

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def run_user_agent(user_profile_path: Path, model: str = "gpt-4o") -> dict:
    """
    Execute the LLM user-agent to generate a search-request form.

    Args:
        user_profile_path: Path to the user_profile.json file.
        model:            OpenAI model to use (default: gpt-4o).

    Returns:
        A dict matching the SEARCH_SCHEMA.

    Raises:
        ValueError:           If the LLM response is invalid JSON or fails schema validation.
        openai.error.OpenAIError: If the API call itself fails.
    """
    # 1) Load user profile
    try:
        raw = user_profile_path.read_text()
        user_profile = json.loads(raw)
    except Exception as e:
        logger.error(f"Failed to load user profile from {user_profile_path}: {e}")
        raise

    # 2) Build messages and call the API
    messages = build_user_agent_messages(json.dumps(user_profile, indent=2))
    logger.info("Calling LLM for user-agent form generation...")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0
    )
    content = resp.choices[0].message.content

    # 3) Parse JSON
    try:
        form = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}\nContent: {content}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    # 4) Validate against schema
    try:
        validate(instance=form, schema=SEARCH_SCHEMA)
    except ValidationError as e:
        logger.error(f"Search form schema validation error: {e.message}")
        raise ValueError(f"Search form failed validation: {e.message}") from e

    logger.info("User-agent form generated and validated successfully.")
    return form


def validate_search_query(
    form: dict,
    query: dict,
    model: str = "gpt-4o",
    temperature: float = 0
) -> dict:
    """
    Ask the LLM to approve the candidate search_query or suggest missing fields.
    Returns a dict with:
      - approved: bool
      - suggestions: {field_name: new_value, …}

    The LLM prompt is defined in VALIDATE_SEARCH_QUERY.
    """
    messages = [
        {"role": "system", "content": VALIDATE_SEARCH_QUERY},
        {
            "role": "user",
            "content": (
                f"FORM: {json.dumps(form, indent=2)}\n"
                f"QUERY: {json.dumps(query, indent=2)}"
            )
        }
    ]

    logger.info("Calling LLM to validate search query...")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )
    content = resp.choices[0].message.content

    try:
        verdict = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from validate_search_query: {e}\nContent: {content}")
        raise ValueError(f"Invalid JSON from validate_search_query: {e}") from e

    return verdict


# Expose a simple agent object for orchestrator
class _UserAgentWrapper:
    def validate_search_query(self, form: dict, query: dict) -> dict:
        return validate_search_query(form, query)


user_agent = _UserAgentWrapper()
