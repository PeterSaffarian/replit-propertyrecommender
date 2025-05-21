"""
property_recommender/data_gathering/features/data_normalizer/prompts.py

Defines the system prompt and function‐calling metadata for the DataNormalizer.
This drives the LLM to convert raw Trade Me property JSON into a clean,
schema‐compliant record.
"""

# System prompt: instructs the LLM on its role and output requirements
SYSTEM_PROMPT = (
    "You are an expert data normalizer for Trade Me property listings. "
    "Using the attached JSON Schema for a normalized property record, "
    "transform the raw property JSON into a single JSON object that "
    "exactly matches the schema. Apply defaults for any missing or "
    "invalid fields, and do not include any additional text or explanation. "
    "Return only the JSON object."
)

# Name of the function the LLM will invoke to return its normalized record
FINAL_FUNCTION_NAME = "normalize_property_record"

# Description of the function’s purpose, used in the OpenAI function‐calling spec
FINAL_FUNCTION_DESCRIPTION = (
    "Normalize a single raw property listing into the standard property_record schema. "
    "The output must be a JSON object matching the attached schema exactly, "
    "with appropriate defaults applied for missing or mistyped fields."
)
