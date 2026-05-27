"""
BaseAgent - Abstract base class for all AI agents in the Resume Intelligence Platform.

Provides a unified interface for calling different LLM providers (OpenAI, Anthropic)
with automatic retry logic, JSON parsing, and output validation.
"""

import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod

import anthropic
from dotenv import load_dotenv

from engine.llm_trace import record_llm_call

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

    def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        *,
        call_label: str = "",
    ) -> str:
        prompt_chars = len(system_prompt) + len(user_message)
        started = time.perf_counter()

        def _log_duration() -> None:
            record_llm_call(
                agent=self.__class__.__name__,
                provider=self.provider,
                model=self.model,
                duration_ms=(time.perf_counter() - started) * 1000,
                prompt_chars=prompt_chars,
                call_label=call_label,
            )

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
                    _log_duration()
                    return response.choices[0].message.content
                except Exception as e:
                    if attempt == 0:
                        logger.warning(
                            "%s: OpenAI API error on attempt 1, retrying. %s",
                            self.__class__.__name__,
                            self._format_exception_detail(e),
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
                    _log_duration()
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

    def _format_exception_detail(self, error: Exception) -> str:
        """Return a concise exception string including root cause details."""
        detail = str(error) or error.__class__.__name__
        root = error.__cause__
        if root:
            root_detail = str(root) or root.__class__.__name__
            if root_detail and root_detail not in detail:
                return f"{detail} | cause: {root_detail}"
        return detail

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

        Handles the common LLM truncation pattern of "key": "value...EOF where
        the unterminated string is dropped along with its dangling key/colon
        and any trailing comma on the previous sibling.

        Returns dict on success, None if unrecoverable.
        """
        in_string = False
        escape = False
        stack: list[str] = []
        cut_pos = len(text)

        for ch in text:
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
                stack.append(ch)
            elif ch in ("}", "]"):
                if stack:
                    stack.pop()

        if in_string:
            last_quote = text.rfind('"', 0, cut_pos)
            if last_quote >= 0:
                quote_count = text.count('"', 0, last_quote + 1)
                if quote_count % 2 == 1:
                    text = text[:last_quote]

        text = self._strip_dangling_key(text)
        text = text.rstrip()
        if text.endswith(","):
            text = text[:-1]

        closers = {"{": "}", "[": "]"}
        while stack:
            text += closers.get(stack.pop(), "")

        try:
            return json.loads(text)
        except Exception:
            return None

    def _strip_dangling_key(self, text: str) -> str:
        """
        Remove a trailing `"key":` (and the comma preceding it) when there is no
        value yet. This is the common shape after `_repair_truncated_json` drops
        an unterminated string value.

        Example input:  '... "name": "Alice", "bio":  '
        Returns:        '... "name": "Alice"'
        """
        stripped = text.rstrip()
        if not stripped.endswith(":"):
            colon_match = re.search(r':\s*$', stripped)
            if not colon_match:
                return text

        key_match = re.search(r',?\s*"[^"\\]*"\s*:\s*$', stripped)
        if not key_match:
            return text

        return stripped[: key_match.start()]

    def validate_output(self, output: dict, required_keys: list[str]) -> None:
        missing = [k for k in required_keys if k not in output]
        if missing:
            raise ValueError(f"{self.__class__.__name__}: missing keys {missing}")
