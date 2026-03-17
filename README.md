# AgentsTeam

A local multi-agent team system that orchestrates AI agents with customizable professional roles to collaborate on complex goals. Agents communicate through a message bus, tasks are scheduled with dependency awareness, and progress is observable in real-time via a web UI.

## Features

- **Multi-Agent Collaboration** - CEO agent decomposes goals into tasks, delegates to specialized agents (Engineer, Designer, PM, QA, Operations), and evaluates completion
- **Dependency-Aware Scheduling** - Tasks express dependencies; the scheduler ensures correct execution order
- **Real-Time Observation** - WebSocket-powered live message feed shows agent activity as it happens
- **Multiple LLM Providers** - Supports Anthropic Claude, OpenAI, and local models (Ollama)
- **Custom Agents** - Create your own agent roles with custom prompts and expertise
- **Session Recovery** - Interrupted sessions resume automatically on restart
- **Goal Queue** - Submit multiple goals; they execute in order

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Web UI)                 │
│  Observation  |  Goals  |  Agents  |  History       │
└──────────┬──────────────────────────┬───────────────┘
           │ REST API                 │ WebSocket
┌──────────▼──────────────────────────▼───────────────┐
│                  FastAPI Server                      │
├─────────────────────────────────────────────────────┤
│  Orchestrator ──▶ Scheduler ──▶ Agent Registry      │
│       │                              │              │
│  State Manager      Message Bus ◀────┘              │
├─────────────────────────────────────────────────────┤
│  LLM Providers: Anthropic │ OpenAI │ Ollama         │
├─────────────────────────────────────────────────────┤
│  SQLite + SQLModel (async)                          │
└─────────────────────────────────────────────────────┘
```

## Predefined Roles

| Role | Key | Responsibility |
|------|-----|----------------|
| CEO | `ceo` | Goal decomposition, task delegation, completion evaluation |
| Product Manager | `product_manager` | Requirements analysis, specifications |
| Full-Stack Engineer | `engineer` | Technical design and implementation |
| UI/UX Designer | `designer` | Interface and experience design |
| QA Engineer | `qa_engineer` | Testing and quality assurance |
| Operations | `operations` | Marketing, growth, and operations |

## Quick Start

### Prerequisites

- Python 3.11+
- At least one LLM API key (Anthropic, OpenAI, or local Ollama)

### Installation

```bash
# Clone the repository
git clone https://github.com/diffusefuturetech/AgentsTeam.git
cd AgentsTeam

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
python -m src.main
```

Open `http://localhost:9000` in your browser.

## Configuration

Edit `.env` to configure:

```bash
# LLM Provider API Keys (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
LOCAL_MODEL_URL=http://localhost:11434

# Database
DATABASE_URL=sqlite+aiosqlite:///agents_team.db

# Server
HOST=0.0.0.0
PORT=9000
LOG_LEVEL=info
```

## How It Works

1. **Submit a Goal** - Describe what you want the team to accomplish
2. **CEO Decomposes** - The CEO agent breaks the goal into tasks with dependencies
3. **Agents Execute** - Each task is dispatched to the assigned agent when dependencies are met
4. **Real-Time Updates** - Watch agent communication in the observation panel
5. **Evaluation** - CEO evaluates completion; you confirm or extend with new instructions

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/goals` | Create a new goal |
| `GET` | `/api/goals` | List goals (optional `?status=` filter) |
| `GET` | `/api/goals/{id}` | Goal details with tasks and progress |
| `POST` | `/api/goals/{id}/pause` | Pause active goal |
| `POST` | `/api/goals/{id}/resume` | Resume paused goal |
| `POST` | `/api/goals/{id}/stop` | Stop goal |
| `POST` | `/api/goals/{id}/confirm` | Confirm goal completion |
| `POST` | `/api/goals/{id}/extend` | Extend goal with new instructions |
| `GET` | `/api/agents` | List agent roles |
| `POST` | `/api/agents` | Create custom agent |
| `GET` | `/api/teams` | List teams |
| `WS` | `/ws/observe` | Real-time observation WebSocket |

## Project Structure

```
src/
├── main.py              # FastAPI app entry point
├── config.py            # Settings (pydantic-settings)
├── core/
│   ├── orchestrator.py  # Main coordination engine
│   ├── message_bus.py   # Message routing & WebSocket broadcast
│   ├── scheduler.py     # Dependency-aware task scheduling
│   └── state_manager.py # Persistence & session recovery
├── agents/
│   ├── base.py          # BaseAgent with LLM integration
│   ├── registry.py      # Agent instance management
│   └── predefined/      # Built-in role definitions
├── providers/
│   ├── anthropic.py     # Claude API
│   ├── openai_provider.py # OpenAI API
│   └── local.py         # Ollama / local models
├── models/              # SQLModel data models
├── api/                 # REST & WebSocket endpoints
└── db/                  # Database initialization & seeding
frontend/
├── index.html           # Main UI (4 tabs)
├── js/                  # App, observation, agents, history modules
└── css/                 # Dark theme styles
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## License

MIT
