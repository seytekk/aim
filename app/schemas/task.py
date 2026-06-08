from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import Priority, SubtaskStatus, TaskStatus


# ── Subtask ──────────────────────────────────────────────────────────────────

class SubtaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)


class SubtaskCreate(SubtaskBase):
    pass


class SubtaskRead(SubtaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    status: SubtaskStatus
    created_at: datetime


# ── Task ─────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    story_points: Optional[int] = Field(None, ge=1, le=100)
    subtasks: List[SubtaskCreate] = Field(default_factory=list)
    risks: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    raw_input: Optional[str] = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    priority: Priority
    story_points: Optional[int]
    status: TaskStatus
    risks: Optional[str]
    notion_page_id: Optional[str]
    notion_page_url: Optional[str]
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    telegram_chat_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    subtasks: List[SubtaskRead]


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


# ── Planner Agent output (LLM JSON schema) ────────────────────────────────────

class PlannerOutput(BaseModel):
    title: str = Field(..., description="Short task title")
    description: str = Field(..., description="Detailed task description")
    priority: Priority = Field(..., description="Task priority")
    story_points: int = Field(..., ge=1, le=100, description="Estimated complexity in story points")
    subtasks: List[str] = Field(..., description="List of subtask titles")
    risks: List[str] = Field(default_factory=list, description="Potential risks or blockers")
