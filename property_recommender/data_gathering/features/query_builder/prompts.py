"""
property_recommender/data_gathering/features/query_builder/prompts.py

Defines the system prompt and function‐calling metadata for the QueryBuilder.
This file drives the LLM to translate a structured user profile into
valid Trade Me Property API query parameters, using attached metadata.
"""

# The system prompt sets the agent’s role, available metadata, and output requirements.
SYSTEM_PROMPT = (
    "You are an expert assistant for constructing Trade Me Property API queries. "
    "Using the attached metadata files (Region, District, Suburb, Attributes), "
    "translate the user's property preference profile into a JSON object "
    "containing valid query parameters for the Property search endpoint. "
    "Only output the JSON object that matches the required schema. "
    "Do not include any additional text or explanation."
)

# Name of the function the LLM will invoke to return its JSON output
FINAL_FUNCTION_NAME = "build_search_params"

# Description of the function’s purpose, used in the OpenAI function‐calling spec
FINAL_FUNCTION_DESCRIPTION = (
    "Generate a JSON object of query parameters for the Trade Me Property API "
    "based on the provided user profile. Valid keys include price_min, price_max, "
    "bedrooms_min, bathrooms_min, region, suburb, property_type, open_homes, and any "
    "other filters supported by the API. The output must exactly match the schema."
)
