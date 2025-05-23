"""
property_recommender/data_gathering/features/user_agent/prompts.py

This module defines the system and user prompts for the LLM-based "User Agent" feature.
The LLM will consume a user profile and a JSON schema (search_request_form.json) and output
strictly a JSON object conforming to that schema, representing the user's property search preferences.
"""

import json
from pathlib import Path

# Load the JSON schema the LLM must adhere to
SCHEMA_FILE = Path(__file__).parent.parent.parent / 'schemas' / 'search_request_form.json'
SEARCH_SCHEMA = json.loads(SCHEMA_FILE.read_text())

SYSTEM_PROMPT = f"""
You are the user's dedicated property search assistant. Act as the user's proxy: interpret their
real estate preferences, make reasonable decisions or educated guesses when details are missing,
and produce exactly one JSON object that follows the provided schema.

Rules:
- You have the authority to decide or infer missing information based on the user's profile.
- You must include at least one location field: "region", "district", or "suburb". If the profile
  mentions a city, map it to "district". If uncertain, default the value into "district".
- Only output valid JSON matching the schema below; do not add extra keys or wrap output in
  markdown or code fences.
- All fields are optional; include only those clearly implied by the user's profile.

JSON Schema (draft-07):
{json.dumps(SEARCH_SCHEMA, indent=2)}
"""

USER_PROMPT_TEMPLATE = """
User Profile (raw JSON):
{user_profile}

Using the schema above, output a JSON object capturing the user's property search criteria.
For location names, try to use the names from the Trade Me metadata (regions, districts, suburbs),
especially the specific formal suburb names for each city.
Deliver only the JSON object, with no explanatory text.
"""

VALIDATE_SEARCH_QUERY = """
You are the user's representative. I will give you:
1. The user's original filled_form JSON (what they wanted).
2. The candidate search_query JSON (endpoint + params).
3. Available suburbs for the district (if any).

Task:
- Verify that params contains "region", "district" and "suburb" IDs.
- Ensure those IDs correctly match the names in the form.
- If everything is present and correct, reply with exactly:
  {"approved": true}

- If suburb is missing or incorrect, suggest alternative suburb names from the available options.
- For common areas like "Central", "City Centre", try variations like "Central City", "CBD", etc.
- Otherwise, reply with exactly:
  {
    "approved": false,
    "suggestions": {
      "<field>": "<new value to retry>"
    }
  }

Your response must be pure JSON, no extra text.
"""


def build_user_agent_messages(user_profile: str) -> list:
    """
    Construct the messages array for the OpenAI ChatCompletion API.

    Args:
        user_profile: JSON string of the user's profile.

    Returns:
        List of messages with 'system' and 'user' roles.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": USER_PROMPT_TEMPLATE.format(user_profile=user_profile)},
    ]
