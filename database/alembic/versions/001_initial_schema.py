"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # asyncpg requires one statement per op.execute() call
    op.execute("DO $$ BEGIN CREATE TYPE priority_enum AS ENUM ('Low', 'Medium', 'High', 'Critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE task_status_enum AS ENUM ('Todo', 'In Progress', 'Done', 'Cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE subtask_status_enum AS ENUM ('Todo', 'Done'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id                  BIGSERIAL PRIMARY KEY,
            title               VARCHAR(512)     NOT NULL,
            description         TEXT,
            priority            priority_enum    NOT NULL DEFAULT 'Medium',
            story_points        INTEGER,
            status              task_status_enum NOT NULL DEFAULT 'Todo',
            risks               TEXT,
            notion_page_id      VARCHAR(256),
            notion_page_url     VARCHAR(1024),
            github_issue_number INTEGER,
            github_issue_url    VARCHAR(1024),
            telegram_chat_id    VARCHAR(64),
            raw_input           TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS subtasks (
            id         BIGSERIAL PRIMARY KEY,
            task_id    BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title      VARCHAR(512) NOT NULL,
            status     subtask_status_enum NOT NULL DEFAULT 'Todo',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_status     ON tasks(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_priority   ON tasks(priority)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_subtasks_task_id ON subtasks(task_id)")


def downgrade() -> None:
    op.execute("DROP INDEX  IF EXISTS ix_subtasks_task_id")
    op.execute("DROP INDEX  IF EXISTS ix_tasks_priority")
    op.execute("DROP INDEX  IF EXISTS ix_tasks_status")
    op.execute("DROP TABLE  IF EXISTS subtasks")
    op.execute("DROP TABLE  IF EXISTS tasks")
    op.execute("DROP TYPE   IF EXISTS subtask_status_enum")
    op.execute("DROP TYPE   IF EXISTS task_status_enum")
    op.execute("DROP TYPE   IF EXISTS priority_enum")
