<!--
Sync Impact Report
- Version change: 0.0.0 → 1.0.0
- Added principles: Skill-Driven Architecture, Incremental Enhancement, Agent Abstraction, Resilient Execution, Local-First, Simplicity
- Added sections: Technology Constraints, Development Workflow
- Templates requiring updates:
  - .specify/templates/plan-template.md ⚠ pending
  - .specify/templates/spec-template.md ⚠ pending
  - .specify/templates/tasks-template.md ⚠ pending
- Follow-up TODOs: none
-->

# WorkAgent 本地化批量任务自动化客户端 Constitution

## Core Principles

### I. Skill-Driven Architecture

所有任务自动化 MUST 以 Skill（技能抽象）为核心单元。Skill 描述"做什么"和"为什么"，而非具体的实现步骤。

- 用户输入（视频示范、文本描述、截图序列）MUST 被分析并提取为结构化的 Skill 对象
- Skill MUST 包含：目标（goal）、关键步骤（key_steps）、可变参数（parameters）、约束条件（constraints）
- Skill MUST 可持久化保存、复用、参数化批量执行
- Skill 是连接"理解用户意图"和"执行自动化"的桥梁，任何新功能 MUST 围绕 Skill 生命周期设计

### II. Incremental Enhancement（增量扩展）

所有新功能 MUST 在现有代码基础上增量添加，禁止推倒重写。

- 现有 FastAPI 后端、Agent 实现、视频分析器、前端 UI 是经过验证的资产，MUST 保留并复用
- 新模块（如批量执行引擎）MUST 通过组合现有组件实现，而非替代它们
- 修改现有文件时 MUST 保持向后兼容，不破坏已有 API 接口签名

### III. Agent Abstraction（Agent 抽象层）

系统 MUST 支持多种执行后端（浏览器、桌面软件），通过统一的 Agent 接口屏蔽差异。

- 所有 Agent MUST 继承 BaseAgent 抽象接口（setup → execute_step → teardown）
- 批量执行引擎 MUST 与具体 Agent 实现解耦，通过 skill_type 路由到对应 Agent
- 新增 Agent 类型时只需实现接口，不应修改执行引擎代码

### IV. Resilient Execution（弹性执行）

批量任务执行 MUST 具备容错能力，单个子任务失败不应导致整批任务终止。

- 批量执行 MUST 支持可配置的错误策略：skip（跳过继续）、stop（立即停止）、retry_once（重试一次）
- 每个子任务的执行结果 MUST 独立记录，包括状态、耗时、错误信息
- 执行过程 MUST 支持暂停（pause）、恢复（resume）、停止（stop）操作
- 所有执行事件 MUST 通过 SSE 实时推送给前端

### V. Local-First（本地优先）

工具 MUST 作为本地应用运行，数据 MUST 存储在本地。

- 所有数据（Skill 库、任务历史、批量任务结果）MUST 使用 SQLite 本地存储
- 不依赖外部服务器或云存储（LLM API 调用除外）
- 启动 MUST 简单：一条命令或一次双击即可启动完整应用

### VI. Simplicity（简洁性）

MUST 选择最简单的实现方案，避免过度工程化。

- 优先使用 Python 标准库和已有依赖，避免引入不必要的新依赖
- 不为假设性的未来需求预先设计，当前需要什么就实现什么（YAGNI）
- 前端保持单页应用（SPA）模式，不引入前端框架，延续现有 vanilla JS 风格

## Technology Constraints

- **后端**: Python 3.11+, FastAPI, uvicorn
- **数据库**: SQLite（标准库 sqlite3）
- **浏览器自动化**: browser-use + Playwright
- **桌面自动化**: PyAutoGUI + pyperclip
- **视觉识别**: RapidOCR (ONNX Runtime), OpenCV, Pillow
- **LLM**: 通过 OpenAI 兼容 API 调用（当前配置 Gemini，MUST 支持切换）
- **前端**: 原生 HTML/CSS/JS，无框架
- **异步模型**: asyncio（所有 Agent 和路由 MUST 为 async）

## Development Workflow

- 每个功能 MUST 先通过 spec-kit 流程（specify → plan → tasks → implement）完成规格设计
- 代码修改 MUST 保持现有文件结构（workAgent/src/、workAgent/static/ 等）
- 新增路由 MUST 注册到 main.py 并遵循现有路由组织方式（workAgent/src/routes/）
- 数据模型 MUST 使用 Pydantic BaseModel，与现有模型风格一致
- API 响应 MUST 使用 JSON 格式，错误使用 HTTPException

## Governance

本 Constitution 是项目所有开发决策的最高指导文件。

- 所有新功能提案 MUST 验证与上述原则的一致性
- 原则的修改 MUST 通过 `/speckit.constitution` 流程记录变更和版本号
- 当原则之间冲突时，优先级：Skill-Driven > Resilient Execution > Simplicity > 其他

**Version**: 1.0.0 | **Ratified**: 2026-03-15 | **Last Amended**: 2026-03-15
