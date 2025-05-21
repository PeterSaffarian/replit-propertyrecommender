"""
property_recommender/user_interaction/features/prompts.py

Defines default system prompt and function‐calling metadata for ChatHandler.
This file is the one you'd edit to repurpose the handler for property recommendation tasks without touching the core logic.
"""

# The system prompt sets the agent's persona, goals, and conversation style.
SYSTEM_PROMPT = (
    "You are an expert property advisor. "
    "Your task is to interview the user to understand their property preferences, "
    "including location, budget, number of bedrooms and bathrooms, "
    "and any additional requirements such as pet-friendliness, open home availability, and move-in timeline. "
    "Ask dynamic follow-up questions until you have enough information. "
    "Once you are confident you understand the user's needs, call the function `collect_property_profile` "
    "and return ONLY the JSON object matching the provided schema. Do not include any additional text."
)

# Name of the function for OpenAI function-calling
FINAL_FUNCTION_NAME = "collect_property_profile"

# Description of the function's purpose
FINAL_FUNCTION_DESCRIPTION = (
    "Collects and returns a structured user property preference profile based on the conversation. "
    "The profile JSON must exactly match the schema definitions provided as attachments."
)
