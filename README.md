# AgentsTeam

A local multi-agent team system that orchestrates AI agents with customizable professional roles to collaborate on complex goals. Agents communicate through a message bus, tasks are scheduled with dependency awareness, and progress is observable in real-time via a web UI.

## Features

- **Multi-Agent Collaboration** - CEO agent decomposes goals into tasks, delegates to specialized agents (Douyin Strategist, Xiaohongshu Specialist, Growth Hacker, AI Citation Strategist, UI Designer, Content Creator), and evaluates completion
- **Tool Calling** - Agents can search the web, fetch URLs, and create artifacts during task execution via provider-native tool calling (OpenAI function_calling, Anthropic tool_use, local text-based fallback)
- **Dependency Result Passing** - Downstream agents automatically receive complete results from upstream tasks, enabling meaningful multi-step collaboration
- **Agent-to-Agent Collaboration** - Agents can request help from other agents mid-task via the `ask_agent` tool, with loop detection (max 3 nested calls)
- **Self-Review** - Optional two-pass output: agents review their own work for completeness, actionability, and relevance before submission
- **Structured Output** - Optional JSON Schema enforcement per agent role, with graceful fallback to free-form text
- **Dependency-Aware Scheduling** - Tasks express dependencies; the scheduler ensures correct execution order
- **Real-Time Observation** - WebSocket-powered live message feed shows agent activity, tool calls, and self-review steps as they happen
- **Multiple LLM Providers** - Supports Anthropic Claude, OpenAI, and local models (Ollama) with provider-agnostic tool support
- **Custom Agents** - Create your own agent roles with custom prompts, expertise, tools, and output schemas
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
│  Tool System: web_search │ web_fetch │ create_artifact│ ask_agent
├─────────────────────────────────────────────────────┤
│  LLM Providers: Anthropic │ OpenAI │ Ollama         │
├─────────────────────────────────────────────────────┤
│  SQLite + SQLModel (async)                          │
└─────────────────────────────────────────────────────┘
```

## Predefined Roles

| Role | Key | Tools | Responsibility |
|------|-----|-------|----------------|
| CEO | `ceo` | — | Goal decomposition, task delegation, completion evaluation |
| Douyin Strategist | `douyin_strategist` | web_search, web_fetch, create_artifact | Short-video marketing, algorithm optimization, livestream commerce |
| Xiaohongshu Specialist | `xiaohongshu_specialist` | web_search, web_fetch, create_artifact, ask_agent | Lifestyle content, aesthetic storytelling, community engagement |
| Growth Hacker | `growth_hacker` | web_search, web_fetch, create_artifact | User acquisition, viral loops, funnel optimization, A/B testing |
| AI Citation Strategist | `ai_citation_strategist` | web_search, web_fetch, create_artifact | AI recommendation optimization (AEO/GEO), citation auditing |
| UI Designer | `ui_designer` | web_search, web_fetch, create_artifact | Design systems, component libraries, accessible interfaces |
| Content Creator | `content_creator` | web_search, web_fetch, create_artifact | Multi-platform content strategy, brand storytelling, SEO content |

## Built-in Tools

| Tool | Description |
|------|-------------|
| `web_search` | Search the web via DuckDuckGo, returns top 5 results with title, URL, and snippet |
| `web_fetch` | Fetch and extract text content from a URL (HTML stripped, max 8000 chars) |
| `create_artifact` | Save a work product (document, plan, report) as a named artifact in the database |
| `ask_agent` | Request help from another agent mid-task (with loop detection, max 3 nested calls) |

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

# Agent Capabilities
MAX_TOOL_ITERATIONS=10              # Max tool call loops per task (prevents infinite loops)
MAX_DEPENDENCY_RESULT_LENGTH=4000   # Max chars per dependency result injection
```

## How It Works

1. **Submit a Goal** - Describe what you want the team to accomplish
2. **CEO Decomposes** - The CEO agent breaks the goal into tasks with dependencies
3. **Agents Execute** - Each task is dispatched to the assigned agent when dependencies are met. Agents can use tools (web search, URL fetch) and request help from other agents during execution
4. **Real-Time Updates** - Watch agent communication, tool calls, and self-review steps in the observation panel
5. **Evaluation** - CEO evaluates completion with human-readable agent names and structured results; you confirm or extend with new instructions

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
│   ├── base.py          # BaseAgent with tool calling loop, self-review, structured output
│   ├── registry.py      # Agent instance management
│   └── predefined/      # Built-in role definitions (7 roles)
├── tools/
│   ├── __init__.py      # ToolRegistry singleton
│   ├── base.py          # ToolDefinition, ToolCall, ToolResult dataclasses
│   ├── web_search.py    # DuckDuckGo web search
│   ├── web_fetch.py     # URL content fetcher
│   ├── create_artifact.py # Artifact creation
│   └── ask_agent.py     # Agent-to-agent collaboration
├── providers/
│   ├── base.py          # Provider interface with tool support
│   ├── anthropic.py     # Claude API (tool_use)
│   ├── openai_provider.py # OpenAI API (function_calling)
│   └── local.py         # Ollama / local models (text-based tool fallback)
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
