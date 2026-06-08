# AI Project Manager

An AI-powered project management system that lets users create fully structured tasks via Telegram, automatically syncing them to Notion and GitHub.

## How It Works

```
User (Telegram) → FastAPI Webhook → PlannerAgent (OpenAI GPT-4o)
    → PostgreSQL  →  Notion Page  →  GitHub Issue  →  Telegram reply
```

1. User sends a message to the Telegram bot (e.g. *"Add Google OAuth"*)
2. The system sends it to GPT-4o which returns structured JSON
3. A task record is stored in PostgreSQL
4. A Notion page is created with subtasks, priority, and risks
5. A GitHub Issue is opened with a checkbox subtask list
6. The structured result is sent back to the user in Telegram

---

## Prerequisites

- Docker & Docker Compose
- A public HTTPS URL (use [ngrok](https://ngrok.com) for local dev)
- Accounts / tokens for: OpenAI, Notion, GitHub, Telegram

---

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/seytekk/ai-project-manager.git
cd ai-project-manager
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Then fill in all values as described in the sections below.

---

### 3. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the token (format: `123456789:AAFxxxxxxx`)
4. Set in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_WEBHOOK_SECRET=any_random_secret_string
   ```

---

### 4. Get an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com)
2. Navigate to **API Keys** → **Create new secret key**
3. Set in `.env`:
   ```
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o
   ```

---

### 5. Create a Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration**, name it "AI Project Manager"
3. Copy the **Internal Integration Token**
4. In your Notion workspace, create a new **Database** (full page)
5. Add these properties to the database:
   - **Name** (title — exists by default)
   - **Priority** (Select: Low / Medium / High / Critical)
   - **Story Points** (Number)
   - **Status** (Select: Todo / In Progress / Done / Cancelled)
   - **GitHub Issue** (URL)
6. Open the database, click **···** → **Add connections** → select your integration
7. Copy the database ID from the URL:
   `https://notion.so/workspace/**DATABASE_ID_HERE**?v=...`
8. Set in `.env`:
   ```
   NOTION_TOKEN=secret_...
   NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### 6. Get a GitHub Token

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Set permissions: **Issues** → Read & Write
4. Set in `.env`:
   ```
   GITHUB_TOKEN=github_pat_...
   GITHUB_OWNER=your-github-username
   GITHUB_REPO=your-repo-name
   ```

---

### 7. Configure Your Public URL

Telegram webhooks require a public HTTPS URL.

**Option A — Production (any cloud/VPS):**
```
BASE_URL=https://yourdomain.com
```

**Option B — Local development with ngrok:**
```bash
ngrok http 8000
# Copy the https://xxxx.ngrok.io URL
```
```
BASE_URL=https://xxxx.ngrok.io
```

---

### 8. Start PostgreSQL

```bash
docker compose up postgres -d
```

---

### 9. Run Database Migrations

```bash
docker compose run --rm migrate
```

Or with a local Python environment:
```bash
pip install -r requirements.txt
alembic upgrade head
```

---

### 10. Run the Application

**With Docker Compose (recommended):**
```bash
docker compose up --build
```

**Local development:**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The app will automatically register the Telegram webhook on startup.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/tasks` | Create task directly |
| `GET` | `/api/v1/tasks` | List all tasks |
| `GET` | `/api/v1/tasks/{id}` | Get task by ID |
| `PATCH` | `/api/v1/tasks/{id}/status` | Update task status |
| `POST` | `/webhook/telegram` | Telegram webhook endpoint |

Interactive docs: `http://localhost:8000/docs`

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show help |
| `/new <task>` | Create a task explicitly |
| Any text | Automatically creates a task |

---

## Project Structure

```
ai-project-manager/
├── app/
│   ├── main.py                    # FastAPI app, lifespan, routers
│   ├── api/routes/
│   │   ├── tasks.py               # REST CRUD endpoints
│   │   └── telegram.py            # Telegram webhook handler
│   ├── agents/
│   │   └── planner_agent.py       # Orchestrates LLM → TaskCreate
│   ├── services/
│   │   ├── openai_service.py      # GPT-4o JSON analysis
│   │   ├── notion_service.py      # Notion page CRUD
│   │   ├── github_service.py      # GitHub issue CRUD
│   │   └── telegram_service.py    # Bot messaging helpers
│   ├── models/task.py             # SQLAlchemy ORM models
│   ├── repositories/
│   │   └── task_repository.py     # DB access layer
│   ├── schemas/task.py            # Pydantic v2 schemas
│   └── core/
│       ├── config.py              # Pydantic Settings
│       ├── database.py            # Async SQLAlchemy engine
│       ├── dependencies.py        # FastAPI DI providers
│       └── logging.py             # Logging setup
├── database/alembic/              # Alembic migrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Architecture Decisions

| Decision | Reasoning |
|----------|-----------|
| **Clean Architecture** | Services, repositories, agents, and routes are strictly separated |
| **Async all the way** | asyncpg + httpx + openai async SDK for maximum throughput |
| **Pydantic v2** | Fast validation, strict JSON schema enforcement for LLM output |
| **Tenacity retries** | All external API calls retry on transient failures |
| **Dependency Injection** | All services injected via FastAPI `Depends()` — easy to test/mock |
| **GPT-4o `json_object` mode** | Forces valid JSON with zero hallucinated keys |

---

## License

MIT
