"""
property_recommender/user_interaction/features/chat_handler/chat_handler.py

Generic ChatHandler: drives dynamic LLM conversations for "interview → assessment" tasks.
Handles:
  - Ingestion of a system prompt
  - Optional attachments (e.g., schema, docs) as system messages  
  - Dynamic Q&A driven by the LLM until it decides to return structured output  
  - JSON parsing and JSON Schema validation of the final output
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import OpenAI
from jsonschema import validate, ValidationError

from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parents[3] / '.env'
load_dotenv(env_path)

# Global OpenAI client, initialized in the constructor
client: Optional[OpenAI] = None


class ChatHandler:
    """
    Generic LLM-driven chat handler for dynamic user interviews that produce
    structured JSON assessments (e.g., property preference profiles).
    """

    def __init__(
        self,
        system_prompt: str,
        function_def: Dict[str, Any],
        schema: Dict[str, Any],
        attachments: Optional[Dict[str, Path]] = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the ChatHandler.

        Args:
            system_prompt: Instruction describing the agent's role and goals.
            function_def: OpenAI function specification dict with keys:
                - name: function name
                - description: what the function does
                - parameters: JSON Schema for the function arguments
            schema: JSON Schema dict to validate the function output against.
            attachments: Optional mapping of attachment names to Path objects.
                         Contents will be sent as additional system messages.
            model: Name of the OpenAI model to use (e.g., "gpt-4o").
            temperature: Sampling temperature for the conversation.
            api_key: OpenAI API key; defaults to OPENAI_API_KEY environment variable.
        """
        global client
        # Determine API key
        if api_key:
            self.api_key = api_key
        elif os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")  # type: ignore
        else:
            raise ValueError("OpenAI API key must be provided or set in environment.")

        # Initialize OpenAI client
        client = OpenAI(api_key=self.api_key)

        self.model = model
        self.temperature = temperature
        self.function_def = function_def
        self.schema = schema

        # Initialize chat history with the system prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Include attachments as extra system messages
        if attachments:
            for name, path in attachments.items():
                try:
                    content = Path(path).read_text(encoding="utf-8")
                except Exception as e:
                    raise FileNotFoundError(f"Failed to read attachment '{name}': {e}")
                self.messages.append({
                    "role": "system",
                    "name": name,
                    "content": f"Attachment '{name}':\n{content}"
                })

    def chat(self) -> Dict[str, Any]:
        """
        Conduct the interactive interview. The LLM drives the conversation until
        it decides to invoke the provided function (via function_call="auto").

        Returns:
            Parsed and schema-validated JSON object from the function call.
        """
        global client
        while True:
            # Query the model with auto function-calling enabled
            response = client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                functions=[self.function_def],
                function_call="auto",
                temperature=self.temperature
            )
            message = response.choices[0].message  # type: ignore

            # If model invokes the function, parse and validate output
            if getattr(message, 'function_call', None):
                raw_args = message.function_call.arguments  # JSON string
                try:
                    result = json.loads(raw_args)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Failed to parse JSON from function_call: {e}\nRaw: {raw_args}"
                    )
                try:
                    validate(instance=result, schema=self.schema)
                except ValidationError as e:
                    raise ValueError(f"Output validation error: {e.message}")
                return result

            # Otherwise, display assistant message and prompt user
            content = message.content
            print(f"\nAssistant: {content}\n")
            user_input = input("You: ")
            # Record user response and continue
            self.messages.append({"role": "user", "content": user_input})

    def reset(self) -> None:
        """
        Reset conversation history, preserving only the initial system messages.
        """
        # Keep system messages only
        self.messages = [m for m in self.messages if m["role"] == "system"]

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Retrieve non-system messages for debugging or testing.

        Returns:
            List of user and assistant messages without system messages.
        """
        return [
            {"role": m["role"], "content": m.get("content", "")}
            for m in self.messages if m["role"] != "system"
        ]


# Example standalone usage
if __name__ == "__main__":
    # Load the property profile schema
    schema_path = Path(__file__).parents[3] / "schemas" / "property_profile.json"
    function_def = {
        "name": "collect_property_profile",
        "description": "Collects a user property preference profile based on conversation.",
        "parameters": json.loads(schema_path.read_text(encoding="utf-8"))
    }
    schema = function_def["parameters"]

    # Read system prompt from file
    system_prompt_path = Path(__file__).parents[2] / "prompts.py"
    # Assuming prompts.py defines SYSTEM_PROMPT constant
    from property_recommender.user_interaction.features.prompts import SYSTEM_PROMPT
    handler = ChatHandler(
        system_prompt=SYSTEM_PROMPT,
        function_def=function_def,
        schema=schema,
        attachments={"property_profile": schema_path}
    )
    profile = handler.chat()
    print("\nFinal profile:")
    print(json.dumps(profile, indent=2))
