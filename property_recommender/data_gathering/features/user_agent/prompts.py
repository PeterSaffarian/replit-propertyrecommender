"""
property_recommender/data_gathering/features/user_agent/prompts.py

This module defines the system and user prompts for the LLM-based "User Agent" feature.
The LLM will consume a user profile and a JSON schema (search_request_form.json) and output
only a JSON object conforming to that schema, representing the user's property search preferences.
"""
import json
from pathlib import Path

# Path to the JSON schema that the LLM must fill
SCHEMA_FILE = Path(__file__).parent.parent.parent / 'schemas' / 'search_request_form.json'
SEARCH_SCHEMA = json.loads(SCHEMA_FILE.read_text())

# System prompt instructing the LLM on its role and the schema
SYSTEM_PROMPT = f"""
You are a property search assistant. Your task is to translate a user's real estate preferences
into a structured JSON object that strictly adheres to the provided JSON schema.

Rules:
- Only output valid JSON that matches the schema (no extra keys).
- All fields are optional; include only those preferences expressed by the user.
- Do not wrap the JSON in markdown or code fences.

Here is the JSON schema (draft-07):
```json
{json.dumps(SEARCH_SCHEMA, indent=2)}
```
"""

# Template for the user prompt that supplies the user's profile
USER_PROMPT_TEMPLATE = """
User Profile (raw JSON):
```
{user_profile}
```

Using the schema above, fill out a JSON object capturing the user's search criteria
(e.g., location, price_range, bedroom_range, etc.).

Deliver ONLY the JSON object. Do NOT add any explanatory text.
"""


def build_user_agent_messages(user_profile: str) -> list:
    """
    Construct the messages array for the OpenAI ChatCompletion API.

    Args:
        user_profile: JSON string of the user's profile.

    Returns:
        List of message dicts for roles 'system' and 'user'.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(user_profile=user_profile)},
    ]
