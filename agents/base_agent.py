"""
BaseAgent - Abstract base class for all AI agents in the Resume Intelligence Platform.

Provides a unified interface for calling different LLM providers (OpenAI, Anthropic)
with automatic retry logic, JSON parsing, and output validation.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod

import anthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(
        self,
        model: str,
        max_tokens: int | None = None,
        provider: str = "openai",
        max_completion_tokens: int | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens if max_tokens is not None else max_completion_tokens
        self.max_completion_tokens = (
            max_completion_tokens if max_completion_tokens is not None else max_tokens
        )
        self.provider = provider

    @abstractmethod
    def run(self, input_dict: dict) -> dict:
        pass

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        if self.provider == "openai":
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set in environment.")

            client = OpenAI(api_key=api_key)

            for attempt in range(2):
                try:
                    token_param = (
                        {"max_completion_tokens": self.max_completion_tokens}
                        if self._uses_max_completion_tokens()
                        else {"max_tokens": self.max_tokens}
                    )
                    response = client.chat.completions.create(
                        model=self.model,
                        **token_param,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    if attempt == 0:
                        logger.warning(
                            "%s: OpenAI API error on attempt 1, retrying. %s",
                            self.__class__.__name__,
                            e,
                        )
                        continue
                    raise

            raise RuntimeError(f"{self.__class__.__name__}: OpenAI LLM call failed after 2 attempts.")

        if self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set in environment.")

            client = anthropic.Anthropic(api_key=api_key)

            for attempt in range(2):
                try:
                    message = client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_message}],
                        temperature=0
                    )
                    return message.content[0].text
                except anthropic.APIError as e:
                    if attempt == 0:
                        logger.warning(
                            "%s: Anthropic API error on attempt 1, retrying. %s",
                            self.__class__.__name__,
                            e,
                        )
                        continue
                    raise

            raise RuntimeError(f"{self.__class__.__name__}: Anthropic LLM call failed after 2 attempts.")

        raise ValueError(
            f"{self.__class__.__name__}: Unknown provider '{self.provider}'. "
            "Must be 'openai' or 'anthropic'."
        )

    def _uses_max_completion_tokens(self) -> bool:
        """Return True for OpenAI model families that reject max_tokens."""
        model = self.model.lower()
        return model.startswith(("gpt-5", "o1", "o3", "o4"))

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        try:
            last_complete = cleaned.rfind('",')
            if last_complete > 0:
                truncated = cleaned[:last_complete + 1] + "}"
                return json.loads(truncated)
        except json.JSONDecodeError:
            pass

        try:
            repaired = self._repair_truncated_json(cleaned)
            if repaired is not None:
                return repaired
        except Exception:
            pass

        try:
            start = cleaned.index("{")
            end = cleaned.rindex("}") + 1
            return json.loads(cleaned[start:end])
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(
                f"{self.__class__.__name__}: JSON parse failed - {cleaned[:200]}"
            ) from e

    def _repair_truncated_json(self, text: str) -> dict | None:
        """
        Attempt to repair JSON truncated mid-stream by the LLM.
        Closes unterminated strings, arrays, and objects.
        Returns dict on success, None if unrecoverable.
        """
        # Track state as we walk the text
        in_string = False
        escape = False
        depth = 0  # brace/bracket nesting
        stack: list[str] = []  # '{' or '['
        cut_pos = len(text)

        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in ("{", "["):
                depth += 1
                stack.append(ch)
            elif ch in ("}", "]"):
                if stack:
                    stack.pop()
                    depth -= 1

        # If still inside a string, truncate to last clean position
        if in_string:
            # Find the last position before the unterminated string started
            # Walk backwards from end to find the opening quote of the unterminated string
            last_quote = text.rfind('"', 0, cut_pos)
            if last_quote >= 0:
                # Count quotes to see if this one is the opener or closer
                quote_count = text.count('"', 0, last_quote + 1)
                if quote_count % 2 == 1:
                    # Odd = opening quote of unterminated string, drop it
                    text = text[:last_quote]

        # Close remaining open brackets/braces
        closers = {"{": "}", "[": "]"}
        while stack:
            text += closers.get(stack.pop(), "")

        try:
            return json.loads(text)
        except Exception:
            return None

    def validate_output(self, output: dict, required_keys: list[str]) -> None:
        missing = [k for k in required_keys if k not in output]
        if missing:
            raise ValueError(f"{self.__class__.__name__}: missing keys {missing}")
