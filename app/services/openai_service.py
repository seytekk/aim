import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from app.core.config import Settings
from app.schemas.task import PlannerOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior software engineering project manager AI.
Your job is to analyze a raw task description and return a strict JSON object.

Rules:
- Output ONLY valid JSON. No markdown, no code blocks, no explanation.
- Follow the exact schema provided.
- Be concise but informative in descriptions.
- Estimate story points using Fibonacci: 1, 2, 3, 5, 8, 13, 21.
- Priority must be one of: Low, Medium, High, Critical.

JSON Schema:
{
  "title": "string",
  "description": "string",
  "priority": "Low|Medium|High|Critical",
  "story_points": integer,
  "subtasks": ["string", ...],
  "risks": ["string", ...]
}"""


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL
        self._max_tokens = settings.OPENAI_MAX_TOKENS
        self._temperature = settings.OPENAI_TEMPERATURE

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def analyze_task(self, raw_text: str) -> PlannerOutput:
        logger.info("Calling OpenAI to analyze task: %s", raw_text[:80])
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Task: {raw_text}"},
                ],
            )
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty content")

        logger.debug("OpenAI raw response: %s", content)
        data = json.loads(content)
        return PlannerOutput.model_validate(data)
