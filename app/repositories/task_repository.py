from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Subtask, Task, TaskStatus
from app.schemas.task import TaskCreate


class TaskRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, data: TaskCreate) -> Task:
        task = Task(
            title=data.title,
            description=data.description,
            priority=data.priority,
            story_points=data.story_points,
            risks=", ".join(data.risks) if isinstance(data.risks, list) else data.risks,
            telegram_chat_id=data.telegram_chat_id,
            raw_input=data.raw_input,
        )
        self._db.add(task)
        await self._db.flush()

        for st in data.subtasks:
            subtask = Subtask(task_id=task.id, title=st.title)
            self._db.add(subtask)

        await self._db.flush()
        await self._db.refresh(task)
        return task

    async def get_by_id(self, task_id: int) -> Optional[Task]:
        result = await self._db.execute(
            select(Task).where(Task.id == task_id).options(selectinload(Task.subtasks))
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Task]:
        result = await self._db.execute(
            select(Task)
            .options(selectinload(Task.subtasks))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(self, task_id: int, status: TaskStatus) -> Optional[Task]:
        task = await self.get_by_id(task_id)
        if task is None:
            return None
        task.status = status
        await self._db.flush()
        await self._db.refresh(task)
        return task

    async def update_external_refs(
        self,
        task_id: int,
        *,
        notion_page_id: Optional[str] = None,
        notion_page_url: Optional[str] = None,
        github_issue_number: Optional[int] = None,
        github_issue_url: Optional[str] = None,
    ) -> Optional[Task]:
        task = await self.get_by_id(task_id)
        if task is None:
            return None
        if notion_page_id is not None:
            task.notion_page_id = notion_page_id
        if notion_page_url is not None:
            task.notion_page_url = notion_page_url
        if github_issue_number is not None:
            task.github_issue_number = github_issue_number
        if github_issue_url is not None:
            task.github_issue_url = github_issue_url
        await self._db.flush()
        await self._db.refresh(task)
        return task
