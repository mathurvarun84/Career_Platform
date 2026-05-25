"""Coaching agent for generating resume bullets from user feedback."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import anthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_BULLET_KEYS = ("bullet", "generated_bullet", "text")


def _parse_llm_json(raw: str) -> dict:
    """Parse JSON from LLM output (handles markdown fences and trailing prose)."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    try:
        start = cleaned.index("{")
        end = cleaned.rindex("}") + 1
        return json.loads(cleaned[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"CoachingAgent: JSON parse failed - {cleaned[:200]}") from exc


def _normalize_bullet(text: str, max_len: int = 200) -> str:
    """Ensure bullet prefix and length cap."""
    bullet = (text or "").strip()
    if not bullet:
        return ""
    if not bullet.startswith("•"):
        bullet = f"• {bullet.lstrip('-* ')}"
    if len(bullet) > max_len:
        bullet = bullet[: max_len - 1].rstrip() + "…"
    return bullet


def _bullet_from_raw_answer(raw_answer: str) -> str:
    """Deterministic fallback when the model call fails."""
    sentence = " ".join(raw_answer.strip().split())
    if not sentence:
        return ""
    if len(sentence) > 180:
        sentence = sentence[:177].rstrip() + "…"
    return _normalize_bullet(sentence)


def _extract_bullet_fields(data: dict) -> tuple[str, bool]:
    """Read bullet text and grounding flag from parsed JSON."""
    bullet = ""
    for key in _BULLET_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            bullet = val.strip()
            break
    grounding = data.get("grounding", data.get("grounding_check", True))
    return _normalize_bullet(bullet), bool(grounding)


def _bullet_from_free_text(content: str, raw_answer: str) -> str:
    """Last-resort extraction from non-JSON model output."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("•"):
            return _normalize_bullet(stripped)
    return _bullet_from_raw_answer(raw_answer)


def bullet_is_meaningful(text: str) -> bool:
    """Reject empty or parser-artifact bullets like '• :'."""
    body = re.sub(r"^•\s*", "", (text or "").strip())
    body = body.strip(":- \t")
    return len(body) >= 10


class CoachingAgent:
    """Generate achievement bullets from user coaching input using Claude."""

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-haiku-4-5-20251001"

    def _call_model(self, prompt: str):
        """Invoke Anthropic synchronously so callers can apply a hard timeout."""
        return self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

    def generate_bullet(
        self,
        section: str,
        gap_reason: str,
        raw_answer: str,
        coaching_question: str,
        skill_category: str,
    ) -> dict:
        """
        Generate a polished achievement bullet from raw user feedback.

        Returns dict with:
        - generated_bullet: str
        - grounding_check: bool (True if grounding is solid)
        - error: optional str (e.g. generation_timeout)
        """

        prompt = f"""Given a resume section and a user's response to a coaching question, generate a polished, measurable achievement bullet point.

CONTEXT:
Section: {section}
Gap to fix: {gap_reason}
Coaching question: {coaching_question}
Skill category: {skill_category}

USER RESPONSE:
{raw_answer}

REQUIREMENTS:
1. Generate a single, concise bullet point (max 200 chars)
2. Use action verbs (Led, Built, Designed, Delivered, etc.)
3. Include metrics or impact when derivable from user input
4. Use placeholders [X%], [N users], [Xms], [₹X Cr ARR] if metrics aren't specified
5. Never invent company names, institutions, or specific years
6. Format as: "• [verb] [object] [impact/metric]"
7. Focus on outcome, not process

Return ONLY a JSON object (no markdown fences, no extra text) with exactly these keys:
- "bullet": the polished bullet text (must include the • prefix)
- "grounding": true if the bullet stays grounded in the user's response, false if significant elaboration was needed"""

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._call_model, prompt)
                response = future.result(timeout=15.0)

            content = response.content[0].text
            try:
                data = _parse_llm_json(content)
                bullet, grounding = _extract_bullet_fields(data)
                if not bullet_is_meaningful(bullet):
                    bullet = _bullet_from_free_text(content, raw_answer)
                    grounding = False
                return {
                    "generated_bullet": bullet,
                    "grounding_check": grounding,
                }
            except (ValueError, json.JSONDecodeError, KeyError, IndexError) as parse_err:
                logger.warning("Coaching JSON parse failed, using text fallback: %s", parse_err)
                bullet = _bullet_from_free_text(content, raw_answer)
                return {
                    "generated_bullet": bullet,
                    "grounding_check": True,
                }
        except FuturesTimeoutError:
            logger.error("Coaching generation timed out after 15 seconds")
            return {
                "generated_bullet": "",
                "grounding_check": False,
                "error": "generation_timeout",
            }
        except Exception as exc:
            logger.error("Coaching generation failed: %s", exc)
            bullet = _bullet_from_raw_answer(raw_answer)
            return {
                "generated_bullet": bullet,
                "grounding_check": False,
            }
