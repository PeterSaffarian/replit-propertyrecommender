#!/usr/bin/env python3
"""
property_recommender/match_reasoning/features/matcher.py

Matcher supports two modes of matching property listings to a user profile via LLM:

1. Batch ranking (`match_batch`): a single LLM call on the full list, returning a
   sorted array of match entries.
2. Individual scoring (`match_individual`): one LLM call per property record, then sort
   locally. Use this when you hit context‐length limits.

By default, `match` is an alias for the chosen method.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI
from json import JSONDecodeError
from jsonschema import validate, ValidationError

from .prompts import SYSTEM_PROMPT, FINAL_FUNCTION_NAME, FINAL_FUNCTION_DESCRIPTION

# Shared OpenAI client
_global_client: Optional[OpenAI] = None


class Matcher:
    """
    Scores and ranks property listings against a user profile.

    Methods:
      - match_batch:      Batch ranking via single LLM call.
      - match_individual: Per-record scoring + local sort.
      - match: alias to the chosen method.
    """

    def __init__(
        self,
        schema_path: Path,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        retry_limit: int = 2,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the Matcher.

        Args:
            schema_path:  Path to property_match.json (defines array-of-objects schema).
            model:        OpenAI model name.
            temperature:  LLM sampling temperature.
            retry_limit:  Number of retries for LLM calls.
            api_key:      OpenAI API key or use OPENAI_API_KEY env var.
        """
        # Load environment from project root .env
        from dotenv import load_dotenv
        env_path = Path(__file__).parents[3] / '.env'
        load_dotenv(env_path)
        
        # API key setup
        if api_key:
            self.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        elif os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")
        else:
            raise ValueError(f"OpenAI API key must be provided or set in {env_path}")

        self.model = model
        self.temperature = temperature
        self.retry_limit = retry_limit

        # Initialize shared client
        global _global_client
        if _global_client is None:
            _global_client = OpenAI(api_key=self.api_key)
        self.client = _global_client

        # Load full match-array schema
        schema_text = Path(schema_path).read_text(encoding="utf-8")
        self.schema: Dict[str, Any] = json.loads(schema_text)

        # Function-calling definition uses the array schema
        self.function_def = {
            "name":        FINAL_FUNCTION_NAME,
            "description": FINAL_FUNCTION_DESCRIPTION,
            "parameters":  self.schema
        }

        # Base system message
        self.base_messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def match_batch(
        self,
        user_profile: Dict[str, Any],
        properties: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Batch ranking: single LLM call on the entire property list.

        Returns:
            A list of match entries (e.g. property_id, score, rationale), already sorted.
        """
        messages = self.base_messages.copy()
        messages.append({
            "role": "system",
            "name": "user_profile",
            "content": json.dumps(user_profile)
        })
        messages.append({
            "role": "system",
            "name": "property_list",
            "content": json.dumps(properties)
        })

        for attempt in range(1, self.retry_limit + 1):
            resp = self.client.chat.completions.create(  # type: ignore
                model=self.model,
                messages=messages,               # type: ignore
                functions=[self.function_def],   # type: ignore
                function_call={"name": FINAL_FUNCTION_NAME},
                temperature=self.temperature,
            )
            msg = resp.choices[0].message  # type: ignore

            if not getattr(msg, "function_call", None):
                messages.append({
                    "role": "user",
                    "content": (
                        "Please return ONLY a JSON object matching the schema "
                        "with a 'matches' array of entries (property_id, score, rationale)."
                    )
                })
                continue

            raw = msg.function_call.arguments
            try:
                result = json.loads(raw)
            except JSONDecodeError as e:
                print(f"Attempt {attempt}: JSON parse error: {e}")
                messages.append({
                    "role": "user",
                    "content": "Invalid JSON. Please return a valid JSON object."
                })
                continue

            # Validate output
            try:
                validate(instance=result, schema=self.schema)
            except ValidationError as ve:
                print(f"Attempt {attempt}: schema validation error: {ve.message}")
                if attempt < self.retry_limit:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Validation error ({ve.message}). Please correct the JSON."
                        )
                    })
                    continue
                else:
                    raise RuntimeError(
                        f"Schema validation failed after {self.retry_limit} attempts: {ve.message}"
                    )

            # Return the list of matches
            return result.get("matches", [])

        raise RuntimeError("Exceeded retries generating batch matches.")

    def match_individual(
        self,
        user_profile: Dict[str, Any],
        properties: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Individual scoring: one LLM call per property, then local sort.

        Returns:
            A sorted list of match entries (property_id, score, rationale).
        """
        matches: List[Dict[str, Any]] = []

        # Extract item schema from the array schema
        item_schema = self.schema["properties"]["matches"]["items"]

        # Build single-item function definition
        item_fn = {
            "name":        FINAL_FUNCTION_NAME,
            "description": FINAL_FUNCTION_DESCRIPTION,
            "parameters":  item_schema
        }

        for prop in properties:
            messages = self.base_messages.copy()
            messages.append({
                "role": "system",
                "name": "user_profile",
                "content": json.dumps(user_profile)
            })
            messages.append({
                "role": "system",
                "name": "property_list",
                "content": json.dumps([prop])
            })

            for attempt in range(1, self.retry_limit + 1):
                resp = self.client.chat.completions.create(  # type: ignore
                    model=self.model,
                    messages=messages,           # type: ignore
                    functions=[item_fn],         # type: ignore
                    function_call={"name": FINAL_FUNCTION_NAME},
                    temperature=self.temperature,
                )
                msg = resp.choices[0].message  # type: ignore

                if not getattr(msg, "function_call", None):
                    messages.append({
                        "role": "user",
                        "content": "Please return ONLY a JSON object (property_id, score, rationale)."
                    })
                    continue

                raw = msg.function_call.arguments
                try:
                    entry = json.loads(raw)
                except JSONDecodeError as e:
                    print(f"Attempt {attempt}: JSON parse error: {e}")
                    messages.append({
                        "role": "user",
                        "content": "Invalid JSON. Please return a single JSON object."
                    })
                    continue

                # Validate entry
                try:
                    validate(instance=entry, schema=item_schema)
                except ValidationError as ve:
                    print(f"Attempt {attempt}: schema validation error: {ve.message}")
                    messages.append({
                        "role": "user",
                        "content": "Validation error; please correct the JSON."
                    })
                    continue

                matches.append(entry)
                break
            else:
                raise RuntimeError(f"Failed to score property with entry: {prop.get('id')}")

        # Sort descending by score
        matches.sort(key=lambda x: x.get("score", 0), reverse=True)
        return matches

    # Alias: choose default behavior here
    match = match_batch  # or switch to match_individual

# Example standalone usage
if __name__ == "__main__":
    import sys
    profile_path = Path(sys.argv[1])
    props_path = Path(sys.argv[2])
    user_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    properties = json.loads(props_path.read_text(encoding="utf-8"))

    matcher = Matcher(
        schema_path=Path(__file__).parents[2] / "schemas" / "property_match.json"
    )

    result = matcher.match(user_profile, properties)
    print(json.dumps(result, indent=2))
