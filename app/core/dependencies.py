from functools import lru_cache
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import Settings, get_settings
from app.repositories.task_repository import TaskRepository
from app.services.openai_service import OpenAIService
from app.services.notion_service import NotionService
from app.services.github_service import GitHubService
from app.services.telegram_service import TelegramService
from app.agents.planner_agent import PlannerAgent


def get_task_repository(db: AsyncSession = Depends(get_db)) -> TaskRepository:
    return TaskRepository(db)


def get_openai_service(settings: Settings = Depends(get_settings)) -> OpenAIService:
    return OpenAIService(settings)


def get_notion_service(settings: Settings = Depends(get_settings)) -> NotionService:
    return NotionService(settings)


def get_github_service(settings: Settings = Depends(get_settings)) -> GitHubService:
    return GitHubService(settings)


def get_telegram_service(settings: Settings = Depends(get_settings)) -> TelegramService:
    return TelegramService(settings)


def get_planner_agent(
    openai_service: OpenAIService = Depends(get_openai_service),
) -> PlannerAgent:
    return PlannerAgent(openai_service)
