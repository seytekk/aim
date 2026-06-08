import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.agents.planner_agent import PlannerAgent
from app.core.config import Settings, get_settings
from app.core.dependencies import (
    get_github_service,
    get_notion_service,
    get_planner_agent,
    get_task_repository,
    get_telegram_service,
)
from app.repositories.task_repository import TaskRepository
from app.services.github_service import GitHubService
from app.services.notion_service import NotionService
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/telegram", tags=["Telegram"])


def _extract_message(update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return update.get("message") or update.get("edited_message")


@router.post("")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
    planner: PlannerAgent = Depends(get_planner_agent),
    repo: TaskRepository = Depends(get_task_repository),
    notion: NotionService = Depends(get_notion_service),
    github: GitHubService = Depends(get_github_service),
    telegram: TelegramService = Depends(get_telegram_service),
) -> Dict[str, str]:
    # Validate secret token
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    update: Dict[str, Any] = await request.json()
    logger.debug("Telegram update: %s", update)

    message = _extract_message(update)
    if not message:
        return {"status": "ignored"}

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()

    if not text:
        return {"status": "ignored"}

    # Handle commands
    if text.startswith("/start"):
        await telegram.send_message(
            chat_id,
            "👋 <b>Welcome to AI Project Manager!</b>\n\nSend me any task description and I'll structure it for you.\n\nType /help for more info.",
        )
        return {"status": "ok"}

    if text.startswith("/help"):
        await telegram.send_help(chat_id)
        return {"status": "ok"}

    # Strip /new prefix if present
    if text.startswith("/new"):
        text = text[4:].strip()
        if not text:
            await telegram.send_message(chat_id, "Please provide a task description after /new")
            return {"status": "ok"}

    # Process task
    await telegram.send_message(chat_id, "⏳ Analyzing your task with AI…")

    try:
        plan, task_create = await planner.plan(text, telegram_chat_id=str(chat_id))
    except Exception as exc:
        logger.error("PlannerAgent failed: %s", exc, exc_info=True)
        await telegram.send_error(chat_id, "Failed to analyze task. Please try again.")
        return {"status": "error"}

    try:
        task = await repo.create(task_create)
    except Exception as exc:
        logger.error("DB task creation failed: %s", exc, exc_info=True)
        await telegram.send_error(chat_id, "Failed to save task to database.")
        return {"status": "error"}

    subtask_titles = [st.title for st in task_create.subtasks]
    risks = plan.risks

    # GitHub
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    try:
        issue_number, issue_url = await github.create_issue(
            title=plan.title,
            description=plan.description,
            subtasks=subtask_titles,
            priority=plan.priority.value,
            story_points=plan.story_points,
            risks=risks,
        )
    except Exception as exc:
        logger.error("GitHub issue creation failed: %s", exc)

    # Notion
    notion_url: Optional[str] = None
    try:
        page_id, notion_url = await notion.create_task_page(
            title=plan.title,
            description=plan.description,
            priority=plan.priority.value,
            story_points=plan.story_points,
            subtasks=subtask_titles,
            risks=risks,
            github_issue_url=issue_url,
        )
        await repo.update_external_refs(
            task.id,
            notion_page_id=page_id,
            notion_page_url=notion_url,
            github_issue_number=issue_number,
            github_issue_url=issue_url,
        )
    except Exception as exc:
        logger.error("Notion page creation failed: %s", exc)

    await telegram.send_task_created(
        chat_id,
        plan=plan,
        task_id=task.id,
        notion_url=notion_url,
        github_url=issue_url,
    )
    return {"status": "ok"}
