import logging
from typing import Optional

from app.schemas.task import PlannerOutput, SubtaskCreate, TaskCreate
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Transforms raw user input into a structured TaskCreate via LLM."""

    def __init__(self, openai_service: OpenAIService) -> None:
        self._openai = openai_service

    async def plan(
        self,
        raw_text: str,
        *,
        telegram_chat_id: Optional[str] = None,
    ) -> tuple[PlannerOutput, TaskCreate]:
        logger.info("PlannerAgent processing: %s", raw_text[:120])

        plan: PlannerOutput = await self._openai.analyze_task(raw_text)

        task_create = TaskCreate(
            title=plan.title,
            description=plan.description,
            priority=plan.priority,
            story_points=plan.story_points,
            subtasks=[SubtaskCreate(title=st) for st in plan.subtasks],
            risks=", ".join(plan.risks) if plan.risks else None,
            telegram_chat_id=telegram_chat_id,
            raw_input=raw_text,
        )

        logger.info(
            "Planned task '%s' | priority=%s | sp=%d | subtasks=%d",
            plan.title,
            plan.priority,
            plan.story_points,
            len(plan.subtasks),
        )
        return plan, task_create
