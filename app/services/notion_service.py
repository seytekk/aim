import logging
from typing import Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential

import httpx

from app.core.config import Settings
from app.models.task import Priority, TaskStatus

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

# Maps our internal status values → Notion's built-in Status option names
STATUS_MAP: dict[str, str] = {
    "Todo": "Not started",
    "In Progress": "In progress",
    "Done": "Done",
    "Cancelled": "Done",
}


class NotionService:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.NOTION_TOKEN
        self._database_id = settings.NOTION_DATABASE_ID
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=NOTION_BASE_URL, headers=self._headers, timeout=30)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8), reraise=True)
    async def create_task_page(
        self,
        *,
        title: str,
        description: str,
        priority: str,
        story_points: int,
        subtasks: list[str],
        risks: list[str],
        github_issue_url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Returns (page_id, page_url)."""
        children = self._build_children(description, subtasks, risks)

        properties: dict = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Priority": {"select": {"name": priority}},
            "Story Points": {"number": story_points},
            "Status": {"status": {"name": STATUS_MAP.get("Todo", "Not started")}},
        }
        if github_issue_url:
            properties["GitHub Issue"] = {"url": github_issue_url}

        payload = {
            "parent": {"database_id": self._database_id},
            "properties": properties,
            "children": children,
        }

        async with self._client() as client:
            resp = await client.post("/pages", json=payload)
            if not resp.is_success:
                logger.error("Notion API error %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
            data = resp.json()

        page_id: str = data["id"]
        page_url: str = data.get("url", "")
        logger.info("Notion page created: %s", page_url)
        return page_id, page_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8), reraise=True)
    async def update_task_status(self, page_id: str, status: str) -> None:
        payload = {
            "properties": {
                "Status": {"status": {"name": STATUS_MAP.get(status, status)}}
            }
        }
        async with self._client() as client:
            resp = await client.patch(f"/pages/{page_id}", json=payload)
            resp.raise_for_status()
        logger.info("Notion page %s status updated to %s", page_id, status)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8), reraise=True)
    async def get_task_page(self, page_id: str) -> dict:
        async with self._client() as client:
            resp = await client.get(f"/pages/{page_id}")
            resp.raise_for_status()
            return resp.json()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_children(self, description: str, subtasks: list[str], risks: list[str]) -> list[dict]:
        blocks: list[dict] = []

        if description:
            blocks.append(self._heading("Description", 2))
            blocks.append(self._paragraph(description))

        if subtasks:
            blocks.append(self._heading("Subtasks", 2))
            for st in subtasks:
                blocks.append(self._todo(st))

        if risks:
            blocks.append(self._heading("Risks & Blockers", 2))
            for risk in risks:
                blocks.append(self._bulleted(risk))

        return blocks

    @staticmethod
    def _heading(text: str, level: int) -> dict:
        key = f"heading_{level}"
        return {
            "object": "block",
            "type": key,
            key: {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    @staticmethod
    def _paragraph(text: str) -> dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }

    @staticmethod
    def _todo(text: str) -> dict:
        return {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "checked": False,
            },
        }

    @staticmethod
    def _bulleted(text: str) -> dict:
        return {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
        }
