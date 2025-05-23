"""
property_recommender/user_interaction/features/prompts.py

Defines the system prompt (persona, goals, style) and function-calling metadata
for our “property interview” ChatHandler. Once enough information has been
gathered, the model will call `collect_property_profile` with a payload
that strictly matches the JSON schema in user_interaction/schemas/property_profile.json.
"""

import json
from pathlib import Path

# load the profile schema that the LLM must adhere to
SCHEMA_FILE = (
    Path(__file__)
    .parent        # .../user_agent
    .parent        # .../features
    .parent        # .../data_gathering
    .parent        # .../property_recommender
    / "user_interaction"
    / "schemas"
    / "property_profile.json"
)
PROFILE_SCHEMA = json.loads(SCHEMA_FILE.read_text())

# how we frame the assistant’s role, tone, and expected behavior
SYSTEM_PROMPT = f"""
You are a professional real-estate interviewer, blending tactical empathy (Chris Voss–style)
with warmth and clarity. Guide an open-ended, human-centric conversation that uncovers
the user’s real needs, priorities, and context around buying or renting a property.

• Use mirroring, labeling, and gentle follow-ups rather than rigid Q&A.
• If the user is uncertain or reluctant, acknowledge it and move on—capture that nuance.
• When confident you’ve heard enough, call the function `collect_property_profile` with a single
  JSON payload matching the schema below (no extra keys, no markdown, no code fences):

{json.dumps(PROFILE_SCHEMA, indent=2)}

Key payload rules:
  • narrative_summary: a free-form paragraph telling the user’s story.
  • structured_needs: only the fields you’re certain of (bedrooms, bathrooms, budget, locations, timeline).
  • key_insights: bullet-style strings for salient facts (e.g. “works from home”, “two young children”).
  • Use numbers for all numeric values.
"""

# Function-calling spec for the LLM
FUNCTIONS = [
    {
        "name": "collect_property_profile",
        "description": (
            "Collects and returns a structured user property preference profile "
            "with keys narrative_summary, structured_needs, and key_insights. "
            "Output must conform exactly to the provided JSON schema."
        ),
        "parameters": PROFILE_SCHEMA,
    }
]
