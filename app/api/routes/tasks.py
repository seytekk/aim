import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    get_github_service,
    get_notion_service,
    get_planner_agent,
    get_task_repository,
)
from app.agents.planner_agent import PlannerAgent
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead, TaskStatusUpdate
from app.services.github_service import GitHubService
from app.services.notion_service import NotionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    repo: TaskRepository = Depends(get_task_repository),
    notion: NotionService = Depends(get_notion_service),
    github: GitHubService = Depends(get_github_service),
) -> TaskRead:
    task = await repo.create(payload)

    subtask_titles = [st.title for st in payload.subtasks]
    risks = payload.risks if isinstance(payload.risks, list) else (payload.risks.split(", ") if payload.risks else [])

    # GitHub
    try:
        issue_number, issue_url = await github.create_issue(
            title=task.title,
            description=task.description or "",
            subtasks=subtask_titles,
            priority=task.priority.value,
            story_points=task.story_points or 0,
            risks=risks,
        )
    except Exception as exc:
        logger.error("GitHub issue creation failed: %s", exc)
        issue_number, issue_url = None, None

    # Notion
    try:
        page_id, page_url = await notion.create_task_page(
            title=task.title,
            description=task.description or "",
            priority=task.priority.value,
            story_points=task.story_points or 0,
            subtasks=subtask_titles,
            risks=risks,
            github_issue_url=issue_url,
        )
    except Exception as exc:
        logger.error("Notion page creation failed: %s", exc)
        page_id, page_url = None, None

    await repo.update_external_refs(
        task.id,
        notion_page_id=page_id,
        notion_page_url=page_url,
        github_issue_number=issue_number,
        github_issue_url=issue_url,
    )

    updated = await repo.get_by_id(task.id)
    return TaskRead.model_validate(updated)


@router.get("", response_model=List[TaskRead])
async def list_tasks(
    limit: int = 50,
    offset: int = 0,
    repo: TaskRepository = Depends(get_task_repository),
) -> List[TaskRead]:
    tasks = await repo.list_all(limit=limit, offset=offset)
    return [TaskRead.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: int,
    repo: TaskRepository = Depends(get_task_repository),
) -> TaskRead:
    task = await repo.get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.patch("/{task_id}/status", response_model=TaskRead)
async def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    repo: TaskRepository = Depends(get_task_repository),
    notion: NotionService = Depends(get_notion_service),
    github: GitHubService = Depends(get_github_service),
) -> TaskRead:
    task = await repo.update_status(task_id, payload.status)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.notion_page_id:
        try:
            await notion.update_task_status(task.notion_page_id, payload.status.value)
        except Exception as exc:
            logger.error("Notion status sync failed: %s", exc)

    if task.github_issue_number:
        try:
            if payload.status.value in ("Done", "Cancelled"):
                await github.close_issue(task.github_issue_number)
        except Exception as exc:
            logger.error("GitHub issue close failed: %s", exc)

    return TaskRead.model_validate(task)
