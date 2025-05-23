#!/usr/bin/env python3
"""
property_recommender/user_interaction/main.py

CLI entrypoint for the user_interaction module.

This script orchestrates the dynamic interview workflow by:
  1. Loading the JSON Schema defining the property preference profile.
  2. Building the OpenAI function definition for schema enforcement.
  3. Attaching additional context documents.
  4. Instantiating the generic ChatHandler.
  5. Running the LLM-driven chat to collect a structured profile.
  6. Writing the resulting JSON profile to disk.
"""
import json
import sys
from os.path import dirname
from pathlib import Path

# Ensure root package path for imports
sys.path.append(dirname(dirname(__file__)))

from property_recommender.user_interaction.features.prompts import (
    SYSTEM_PROMPT,
    FINAL_FUNCTION_NAME,
    FINAL_FUNCTION_DESCRIPTION,
)
from property_recommender.user_interaction.features.chat_handler.chat_handler import ChatHandler


def main():
    """
    Main entrypoint for collecting and persisting the user property preference profile.

    Steps:
      1. Load JSON Schema from `schemas/property_profile.json`.
      2. Construct the OpenAI function definition.
      3. Define attachments for additional context (schema file).
      4. Instantiate ChatHandler with prompts, schema, and attachments.
      5. Run the chat loop to obtain the structured profile.
      6. Write `property_profile.json` to current directory.
    """
    # 1. Load the JSON Schema
    schema_path = Path(__file__).parent / "schemas" / "property_profile.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: Schema file not found at {schema_path}")
        return
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON Schema: {e}")
        return

    # 2. Build the function definition for OpenAI function-calling
    function_def = {
        "name": FINAL_FUNCTION_NAME,
        "description": FINAL_FUNCTION_DESCRIPTION,
        "parameters": schema,
    }

    # 3. Attach additional context documents
    attachments = {"property_profile_schema": schema_path}

    # 4. Instantiate the ChatHandler
    handler = ChatHandler(
        system_prompt=SYSTEM_PROMPT,
        function_def=function_def,
        schema=schema,
        attachments=attachments,
    )

    # 5. Run the chat loop to collect the user profile
    try:
        profile = handler.chat()
    except Exception as e:
        print(f"Error during chat interaction: {e}")
        return

    # 6. Persist the profile to disk
    output_path = Path.cwd() / "user_profile.json"
    try:
        output_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        print(f"✅ Profile successfully saved to {output_path}")
    except Exception as e:
        print(f"Error writing profile to disk: {e}")


if __name__ == "__main__":
    main()
