import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.schemas.task import PlannerOutput

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.TELEGRAM_BOT_TOKEN
        self._base = f"{TELEGRAM_API_BASE}/bot{self._token}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=15)

    async def set_webhook(self, webhook_url: str, secret: str) -> bool:
        async with self._client() as client:
            resp = await client.post(
                "/setWebhook",
                json={"url": webhook_url, "secret_token": secret, "drop_pending_updates": True},
            )
            data = resp.json()
            ok: bool = data.get("ok", False)
            logger.info("Telegram webhook set: %s → %s", webhook_url, ok)
            return ok

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6), reraise=True)
    async def send_message(self, chat_id: str | int, text: str, parse_mode: str = "HTML") -> None:
        async with self._client() as client:
            resp = await client.post(
                "/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
            resp.raise_for_status()

    async def send_task_created(
        self,
        chat_id: str | int,
        *,
        plan: PlannerOutput,
        task_id: int,
        notion_url: Optional[str],
        github_url: Optional[str],
    ) -> None:
        subtasks_text = "\n".join(f"  • {st}" for st in plan.subtasks)
        risks_text = "\n".join(f"  ⚠️ {r}" for r in plan.risks) if plan.risks else "  None identified"

        links: list[str] = []
        if notion_url:
            links.append(f'📄 <a href="{notion_url}">Notion Page</a>')
        if github_url:
            links.append(f'🐙 <a href="{github_url}">GitHub Issue</a>')
        links_text = "  " + "\n  ".join(links) if links else "  (pending)"

        text = (
            f"✅ <b>Task #{task_id} Created</b>\n\n"
            f"📌 <b>{plan.title}</b>\n"
            f"{plan.description}\n\n"
            f"📊 <b>Priority:</b> {plan.priority.value}\n"
            f"🎯 <b>Story Points:</b> {plan.story_points}\n\n"
            f"📋 <b>Subtasks:</b>\n{subtasks_text}\n\n"
            f"🚧 <b>Risks:</b>\n{risks_text}\n\n"
            f"🔗 <b>Links:</b>\n{links_text}"
        )
        await self.send_message(chat_id, text)

    async def send_error(self, chat_id: str | int, message: str) -> None:
        await self.send_message(chat_id, f"❌ <b>Error:</b> {message}")

    async def send_help(self, chat_id: str | int) -> None:
        text = (
            "🤖 <b>AI Project Manager Bot</b>\n\n"
            "<b>Commands:</b>\n"
            "  /start — Start the bot\n"
            "  /help — Show this help message\n"
            "  /new &lt;task&gt; — Create a task explicitly\n\n"
            "<b>Or just send me a plain message</b> and I'll create a task automatically!\n\n"
            "<i>Example:</i> <code>Add Google OAuth authentication</code>"
        )
        await self.send_message(chat_id, text)
