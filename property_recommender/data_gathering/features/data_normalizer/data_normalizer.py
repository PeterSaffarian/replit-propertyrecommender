#!/usr/bin/env python3
"""
property_recommender/data_gathering/features/data_normalizer/data_normalizer.py

DataNormalizer processes each raw property record via LLM function-calling,
applies schema-based defaults for missing or mistyped fields, retries on parse
or validation errors, and validates the final output against the JSON Schema.
Includes progress logging to show normalization progress.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from openai import OpenAI
from json import JSONDecodeError
from jsonschema import validate, ValidationError

from .prompts import SYSTEM_PROMPT, FINAL_FUNCTION_NAME, FINAL_FUNCTION_DESCRIPTION

# Shared OpenAI client across instances
_global_client: Optional[OpenAI] = None


class DataNormalizer:
    """
    Normalizes raw Property API data record-by-record via LLM function-calling,
    applies default values for missing or mistyped fields, retries as needed,
    and validates against the property_record schema. Prints progress for feedback.
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
        Initialize the DataNormalizer.

        Args:
            schema_path:  Path to the JSON Schema for normalized property records.
            model:        OpenAI model name (e.g. "gpt-4o").
            temperature:  Sampling temperature for LLM.
            retry_limit:  Number of retry attempts on parse/validation errors.
            api_key:      OpenAI API key; falls back to OPENAI_API_KEY env var.
        """
        # Configure API key
        if api_key:
            self.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        elif os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")
        else:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY.")

        # Initialize shared client once
        global _global_client
        if _global_client is None:
            _global_client = OpenAI(api_key=self.api_key)
        self.client = _global_client

        self.model = model
        self.temperature = temperature
        self.retry_limit = retry_limit

        # Load the JSON schema for normalized records
        schema_text = Path(schema_path).read_text(encoding="utf-8")
        self.schema: Dict[str, Any] = json.loads(schema_text)

        # Prepare the OpenAI function definition
        self.function_def = {
            "name": FINAL_FUNCTION_NAME,
            "description": FINAL_FUNCTION_DESCRIPTION,
            "parameters": self.schema
        }

        # Base messages: system prompt + schema attachment
        self.base_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "name": "schema", "content": schema_text},
        ]

    def _apply_schema_defaults(self, record: Dict[str, Any]) -> None:
        """
        Apply type-appropriate defaults for any missing or mismatched fields
        according to the schema.
        """
        props = self.schema.get("properties", {})
        for key, subschema in props.items():
            allowed = subschema.get("type")
            types = allowed if isinstance(allowed, list) else [allowed]
            val = record.get(key, None)

            # If null is allowed and val is None, skip
            if val is None and "null" in types:
                continue

            # Type-check helper
            def matches_type(v: Any, t: str) -> bool:
                return (
                    (t == "array"   and isinstance(v, list)) or
                    (t == "object"  and isinstance(v, dict)) or
                    (t == "string"  and isinstance(v, str)) or
                    (t == "integer" and isinstance(v, int) and not isinstance(v, bool)) or
                    (t == "number"  and isinstance(v, (int, float))) or
                    (t == "boolean" and isinstance(v, bool)) or
                    (t == "null"    and v is None)
                )

            # If missing or wrong type, assign a default
            if val is None or not any(matches_type(val, t) for t in types):
                if "array" in types:
                    record[key] = []
                elif "object" in types:
                    record[key] = {}
                elif "string" in types:
                    record[key] = ""
                elif "integer" in types or "number" in types:
                    record[key] = 0
                elif "boolean" in types:
                    record[key] = False
                else:
                    record[key] = None

    def _normalize_one(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single raw record via the LLM, apply defaults,
        retry on JSON or validation errors, and return a compliant dict.
        """
        messages = list(self.base_messages)
        messages.append({
            "role": "system",
            "name": "raw_record",
            "content": json.dumps(record)
        })

        for attempt in range(1, self.retry_limit + 1):
            # 1. Invoke the LLM
            response = self.client.chat.completions.create(  # type: ignore
                model=self.model,
                messages=messages,                # type: ignore
                functions=[self.function_def],    # type: ignore
                function_call={"name": FINAL_FUNCTION_NAME},
                temperature=self.temperature,
            )
            msg = response.choices[0].message  # type: ignore

            # 2. Ensure the function is called
            if not getattr(msg, "function_call", None):
                messages.append({
                    "role": "user",
                    "content": (
                        "Please return ONLY the JSON object matching the schema—"
                        "no extra text."
                    )
                })
                continue

            # 3. Parse the JSON output
            raw_output = msg.function_call.arguments
            try:
                normalized = json.loads(raw_output)
            except JSONDecodeError as e:
                print(f"Attempt {attempt}: JSON parse error: {e}")
                messages.append({
                    "role": "user",
                    "content": "Invalid JSON. Please return only the JSON object."
                })
                continue

            # 4. Unwrap single-item arrays
            if isinstance(normalized, list) and len(normalized) == 1:
                normalized = normalized[0]

            if not isinstance(normalized, dict):
                messages.append({
                    "role": "user",
                    "content": "Expected a JSON object. Please correct."
                })
                continue

            # 5. Apply schema defaults
            self._apply_schema_defaults(normalized)

            # 6. Validate against schema
            try:
                validate(instance=normalized, schema=self.schema)
                return normalized
            except ValidationError as ve:
                print(f"Attempt {attempt}: validation error: {ve.message}")
                if attempt < self.retry_limit:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Validation error ({ve.message}). "
                            "Please correct your JSON output."
                        )
                    })
                    continue
                else:
                    raise RuntimeError(
                        f"Failed to validate record after {self.retry_limit} attempts: {ve.message}"
                    )

        # All retries exhausted
        raise RuntimeError("Exceeded retry limit normalizing record.")

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Normalize a list (or single) of raw records, logging progress.

        Args:
            raw_data: A list of raw record dicts or a single dict.

        Returns:
            A list of validated, normalized record dicts.
        """
        records = raw_data if isinstance(raw_data, list) else [raw_data]
        total = len(records)
        cleaned: List[Dict[str, Any]] = []

        for idx, rec in enumerate(records, start=1):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts} - ⏳ Normalizing record {idx}/{total}...")
            normalized = self._normalize_one(rec)
            cleaned.append(normalized)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{ts} - ✅ Record {idx}/{total} normalized.")

        return cleaned
