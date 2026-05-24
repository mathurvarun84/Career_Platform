"""Coaching agent for generating resume bullets from user feedback."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import anthropic
import json
import logging

logger = logging.getLogger(__name__)


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
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
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
1. Generate a single, concise bullet point (max 150 chars)
2. Use action verbs (Led, Built, Designed, Delivered, etc.)
3. Include metrics or impact when derivable from user input
4. Use placeholders [X%], [N users], [Xms], [₹X Cr ARR] if metrics aren't specified
5. Never invent company names, institutions, or specific years
6. Format as: "• [verb] [object] [impact/metric]"
7. Focus on outcome, not process

Generate the bullet and return a JSON object with:
- "bullet": the polished bullet text
- "grounding": true if the bullet stays grounded in the user's response, false if significant elaboration was needed"""

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._call_model, prompt)
                response = future.result(timeout=10.0)

            content = response.content[0].text
            try:
                data = json.loads(content)
                bullet = data.get("bullet", "").strip()
                grounding = data.get("grounding", True)

                # Clean up bullet if needed
                if bullet and not bullet.startswith("•"):
                    bullet = "• " + bullet

                return {
                    "generated_bullet": bullet,
                    "grounding_check": grounding,
                }
            except json.JSONDecodeError:
                # Fallback: parse bullet from response
                lines = content.split("\n")
                bullet = next(
                    (line.strip() for line in lines if line.strip().startswith("•")),
                    "• " + content.split("bullet")[1].split('"')[1]
                    if 'bullet' in content else "",
                )
                return {
                    "generated_bullet": bullet if bullet else "• " + raw_answer[:100],
                    "grounding_check": True,
                }
        except FuturesTimeoutError:
            logger.error("Coaching generation timed out after 10 seconds")
            return {
                "generated_bullet": "",
                "grounding_check": False,
                "error": "generation_timeout",
            }
        except Exception as e:
            logger.error(f"Coaching generation failed: {e}")
            # Fallback: return user's answer as bullet
            bullet = "• " + raw_answer.strip()[:150]
            if not bullet.startswith("•"):
                bullet = "• " + bullet
            return {
                "generated_bullet": bullet,
                "grounding_check": False,
            }
