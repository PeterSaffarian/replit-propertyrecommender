#!/usr/bin/env python3
"""
property_recommender/data_gathering/features/query_builder/query_builder.py

QueryBuilder dynamically constructs Trade Me Property API query parameters
from a user profile using the OpenAI API.

Responsibilities:
  - Load Trade Me metadata (regions, districts, suburbs, property attributes).
  - Use the LLM to build initial search parameters based on a structured user profile.
  - Offer a refine method to adjust those parameters given user feedback.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI
from property_recommender.data_gathering.providers.trademe_api import load_metadata

# After setting OPENAI_API_KEY, we initialize this once
_global_client: Optional[OpenAI] = None

from .prompts import SYSTEM_PROMPT, FINAL_FUNCTION_NAME, FINAL_FUNCTION_DESCRIPTION

# Names of cached metadata files (loaded via load_metadata)
_METADATA_NAMES = ["Region", "District", "Suburb", "Attributes"]


class QueryBuilder:
    """
    Builds and refines Trade Me Property API query parameters.

    Workflow:
      1. init: load system prompt, metadata attachments, and LLM client.
      2. build_params(profile): generate initial parameters from user profile.
      3. refine_params(prev_params, feedback): adjust parameters based on user feedback.

    Both methods use function-calling to return a JSON object of parameters.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        api_key: Optional[str] = None,
        sandbox: bool = True,
    ):
        """
        Initialize the QueryBuilder.

        Args:
            model:        OpenAI model name.
            temperature:  Sampling temperature for LLM responses.
            api_key:      OpenAI API key (or set OPENAI_API_KEY env var).
            sandbox:      If True, metadata will be loaded from sandbox caches.
        """
        # 1. Configure API key
        if api_key:
            self.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        elif os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")
        else:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY."
            )

        # 2. Initialize shared OpenAI client
        global _global_client
        if _global_client is None:
            _global_client = OpenAI(api_key=self.api_key)
        self.client = _global_client
        self.model = model
        self.temperature = temperature
        self.sandbox = sandbox

        # 3. Build the function definition for LLM function-calling
        self.function_def = {
            "name": FINAL_FUNCTION_NAME,
            "description": FINAL_FUNCTION_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": True
            }
        }

        # 4. Assemble base messages: system prompt + metadata attachments
        self.base_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Attach each metadata JSON so the LLM can map human input to codes
        for name in _METADATA_NAMES:
            data = load_metadata(name)  # will raise if not fetched
            self.base_messages.append({
                "role": "system",
                "name": name,
                "content": json.dumps(data)
            })

        # Placeholder for the last profile, used in refine_params
        self._last_profile: Optional[Dict[str, Any]] = None

    def build_params(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate initial API query parameters from a user profile.

        Args:
            profile: Structured user profile dict (from Module 1).

        Returns:
            Dict[str, Any]: JSON-compatible dict of query parameters
                             (e.g. price_min, bedrooms_min, suburb).
        """
        self._last_profile = profile

        # 1. Copy base messages and append the user profile
        messages = list(self.base_messages)
        messages.append({
            "role": "user",
            "name": "user_profile",
            "content": json.dumps(profile)
        })

        # 2. Invoke the LLM with function-calling
        response = self.client.chat.completions.create(  # type: ignore
            model=self.model,
            messages=messages,             # type: ignore
            functions=[self.function_def], # type: ignore
            function_call={"name": FINAL_FUNCTION_NAME},
            temperature=self.temperature
        )
        message = response.choices[0].message  # type: ignore

        # 3. Extract and parse the function arguments JSON
        if not getattr(message, "function_call", None):
            raise RuntimeError("LLM did not invoke the parameter-building function.")

        raw_args = message.function_call.arguments
        try:
            params = json.loads(raw_args)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM output: {e}\nRaw: {raw_args}")

        return params

    def refine_params(
        self,
        prev_params: Dict[str, Any],
        feedback: str
    ) -> Dict[str, Any]:
        """
        Refine existing parameters based on user feedback.

        Args:
            prev_params: Dict of previously generated parameters.
            feedback:    Natural-language feedback to adjust the search.

        Returns:
            Dict[str, Any]: New JSON-compatible parameters dict.
        """
        if self._last_profile is None:
            raise RuntimeError("Cannot refine before build_params() is called.")

        # 1. Rebuild messages: system, metadata, profile, previous params, then feedback
        messages = list(self.base_messages)
        messages.append({
            "role": "user",
            "name": "user_profile",
            "content": json.dumps(self._last_profile)
        })
        messages.append({
            "role": "assistant",
            "name": "previous_params",
            "content": json.dumps(prev_params)
        })
        messages.append({
            "role": "user",
            "content": f"Please refine the above parameters based on this feedback: {feedback}"
        })

        # 2. Invoke LLM again
        response = self.client.chat.completions.create(  # type: ignore
            model=self.model,
            messages=messages,             # type: ignore
            functions=[self.function_def], # type: ignore
            function_call={"name": FINAL_FUNCTION_NAME},
            temperature=self.temperature
        )
        message = response.choices[0].message  # type: ignore

        if not getattr(message, "function_call", None):
            raise RuntimeError("LLM did not invoke the refine function.")

        raw_args = message.function_call.arguments
        try:
            new_params = json.loads(raw_args)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM output: {e}\nRaw: {raw_args}")

        return new_params
