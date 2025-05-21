"""
property_recommender/match_reasoning/features/prompts.py

Defines the system prompt and function‐calling metadata for the Matcher.
This drives the LLM to score and rank property listings against the user profile.
"""

# System prompt: instructs the LLM on its role and expected output format
SYSTEM_PROMPT = (
    "You are an expert real estate matching specialist. "
    "Given a user’s property preference profile and a list of property listings, "
    "evaluate each listing’s fit and produce a JSON object with a 'matches' array. "
    "Each match entry must contain:\n"
    "  - property_id: the listing’s unique identifier\n"
    "  - score: a float between 0 and 1 indicating how well it meets the user’s needs\n"
    "  - rationale: a brief explanation of why you scored it that way\n"
    "Return ONLY the JSON object matching the attached schema—no extra text."
)

# Name of the function the LLM will invoke to return its matches
FINAL_FUNCTION_NAME = "generate_property_matches"

# Description of the function’s purpose, used in the OpenAI function‐calling spec
FINAL_FUNCTION_DESCRIPTION = (
    "Generate a JSON object containing a 'matches' array of property match entries "
    "based on the provided user profile and property list. "
    "Each entry must include property_id, score, and rationale, and the output "
    "must conform exactly to the schema."
)
