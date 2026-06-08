"""
Local polling runner — use instead of webhook for local development.
Runs the FastAPI app + Telegram polling together.
Usage: python3 poll.py
"""
import asyncio
import logging
import os
import httpx

# Connect to Docker postgres exposed on 5433 (5432 is taken by local Mac postgres)
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5433/ai_pm"

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.database import AsyncSessionFactory
from app.repositories.task_repository import TaskRepository
from app.services.openai_service import OpenAIService
from app.services.notion_service import NotionService
from app.services.github_service import GitHubService
from app.services.telegram_service import TelegramService
from app.agents.planner_agent import PlannerAgent

setup_logging(debug=True)
logger = logging.getLogger("poller")

settings = get_settings()
TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def delete_webhook() -> None:
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/deleteWebhook", json={"drop_pending_updates": True})
        logger.info("Webhook deleted — polling mode active")


async def get_updates(offset: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=35) as client:
        resp = await client.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 30, "limit": 100},
        )
        data = resp.json()
        return data.get("result", []) if data.get("ok") else []


async def handle_update(update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()
    if not text:
        return

    telegram = TelegramService(settings)

    if text.startswith("/start"):
        await telegram.send_message(
            chat_id,
            "👋 <b>Welcome to AI Project Manager!</b>\n\nSend me any task and I'll structure it.\n\nType /help for more info.",
        )
        return

    if text.startswith("/help"):
        await telegram.send_help(chat_id)
        return

    if text.startswith("/new"):
        text = text[4:].strip()
        if not text:
            await telegram.send_message(chat_id, "Please provide a task after /new")
            return

    await telegram.send_message(chat_id, "⏳ Analyzing your task with AI…")

    openai_svc = OpenAIService(settings)
    notion_svc = NotionService(settings)
    github_svc = GitHubService(settings)
    planner = PlannerAgent(openai_svc)

    try:
        plan, task_create = await planner.plan(text, telegram_chat_id=str(chat_id))
    except Exception as exc:
        logger.error("Planner failed: %s", exc, exc_info=True)
        await telegram.send_error(chat_id, "Failed to analyze task. Please try again.")
        return

    async with AsyncSessionFactory() as session:
        repo = TaskRepository(session)
        task = await repo.create(task_create)
        await session.commit()

    subtask_titles = [st.title for st in task_create.subtasks]
    risks = plan.risks

    issue_number, issue_url = None, None
    try:
        issue_number, issue_url = await github_svc.create_issue(
            title=plan.title,
            description=plan.description,
            subtasks=subtask_titles,
            priority=plan.priority.value,
            story_points=plan.story_points,
            risks=risks,
        )
    except Exception as exc:
        logger.error("GitHub failed: %s", exc)

    notion_url = None
    try:
        page_id, notion_url = await notion_svc.create_task_page(
            title=plan.title,
            description=plan.description,
            priority=plan.priority.value,
            story_points=plan.story_points,
            subtasks=subtask_titles,
            risks=risks,
            github_issue_url=issue_url,
        )
        async with AsyncSessionFactory() as session:
            repo = TaskRepository(session)
            await repo.update_external_refs(
                task.id,
                notion_page_id=page_id,
                notion_page_url=notion_url,
                github_issue_number=issue_number,
                github_issue_url=issue_url,
            )
            await session.commit()
    except Exception as exc:
        logger.error("Notion failed: %s", exc)

    await telegram.send_task_created(
        chat_id,
        plan=plan,
        task_id=task.id,
        notion_url=notion_url,
        github_url=issue_url,
    )


async def main() -> None:
    await delete_webhook()
    offset = 0
    logger.info("Polling started… send a message to your bot")

    while True:
        try:
            updates = await get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                await handle_update(update)
        except Exception as exc:
            logger.error("Polling error: %s", exc)
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
