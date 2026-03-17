# AgentsTeam - 本地多Agent团队系统

一个支持自定义专业角色的本地多Agent协作系统，基于 FastAPI + WebSocket 实现实时观察与交互。

## 快速开始

### 环境要求

- Python 3.11+
- (可选) Ollama，用于本地模型推理

### 安装步骤

```bash
# 1. 克隆项目并进入目录
git clone <repo-url>
cd AgentsTeam

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -e .

# 4. 安装开发依赖（可选）
pip install -e ".[dev]"

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 配置说明

编辑 `.env` 文件，至少配置一个 LLM API Key：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Claude 模型 API Key（与 OpenAI 二选一） | 空 |
| `OPENAI_API_KEY` | OpenAI 模型 API Key（与 Anthropic 二选一） | 空 |
| `LOCAL_MODEL_URL` | 本地 Ollama 服务地址 | `http://localhost:11434` |
| `DATABASE_URL` | SQLite 数据库路径 | `sqlite+aiosqlite:///agents_team.db` |
| `HOST` | 服务绑定地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |
| `LOG_LEVEL` | 日志级别 | `info` |

### 启动服务

```bash
python -m src.main
```

服务启动后会自动初始化数据库并启动 Orchestrator。

## 使用指南

浏览器打开 `http://localhost:8000`，界面包含 3 个主要标签页：

- **实时观察** - 通过 WebSocket 实时查看 Agent 对话与工作状态
- **目标管理** - 创建、暂停、恢复、停止目标任务
- **Agent 管理** - 创建和配置 Agent 角色，组建团队

基本工作流：
1. 在「Agent 管理」中创建所需的 Agent 角色
2. 在「目标管理」中创建一个目标，Agent 团队将自动开始协作
3. 在「实时观察」中查看 Agent 之间的实时对话

## API 概览

### 目标管理 `/api/goals`

- `POST /api/goals` - 创建目标
- `GET /api/goals` - 获取目标列表
- `GET /api/goals/{goal_id}` - 获取目标详情
- `POST /api/goals/{goal_id}/pause` - 暂停目标
- `POST /api/goals/{goal_id}/resume` - 恢复目标
- `POST /api/goals/{goal_id}/stop` - 停止目标
- `POST /api/goals/{goal_id}/confirm` - 确认目标
- `POST /api/goals/{goal_id}/extend` - 扩展目标
- `POST /api/goals/{goal_id}/respond` - 响应目标

### Agent 管理 `/api/agents`

- `GET /api/agents` - 获取 Agent 列表
- `POST /api/agents` - 创建 Agent
- `PUT /api/agents/{agent_id}` - 更新 Agent
- `DELETE /api/agents/{agent_id}` - 删除 Agent

### 团队管理 `/api/teams`

- `GET /api/teams` - 获取团队列表
- `POST /api/teams` - 创建团队
- `PUT /api/teams/{team_id}/members` - 更新团队成员

### 历史记录 `/api/sessions`

- `GET /api/sessions/{session_id}/messages` - 获取会话消息
- `GET /api/sessions/{session_id}/artifacts` - 获取会话产出物

### 实时观察

- `WebSocket /ws/observe` - 实时观察 Agent 工作状态

交互式 API 文档：`http://localhost:8000/docs`

## 开发

```bash
# 运行测试
pytest

# 代码检查
ruff check src/
```
