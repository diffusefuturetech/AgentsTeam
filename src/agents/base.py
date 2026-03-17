import json
import logging
from src.models.agent import AgentRole
from src.providers import get_provider, LLMMessage

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents in the team."""

    def __init__(self, role: AgentRole):
        self.role = role
        self.provider = get_provider(role.provider_name, role.model_name)

    @property
    def role_key(self) -> str:
        return self.role.role_key

    @property
    def name(self) -> str:
        return self.role.name

    async def process_message(self, goal: str, task_description: str, context: list[dict]) -> str:
        """Process a task and return the result.

        Args:
            goal: The overall goal being worked on
            task_description: The specific task/request for this agent
            context: List of prior messages for context [{"role": "...", "sender": "...", "content": "..."}]
        """
        system_prompt = self.role.system_prompt.replace("{goal}", goal)

        messages = [LLMMessage(role="system", content=system_prompt)]

        # Add context messages
        for msg in context[-20:]:  # Last 20 messages for context window
            role = "assistant" if msg.get("sender") == self.role_key else "user"
            content = msg["content"]
            if msg.get("sender") and msg["sender"] != self.role_key:
                content = f"[From {msg['sender']}]: {content}"
            messages.append(LLMMessage(role=role, content=content))

        # Add current task
        messages.append(LLMMessage(role="user", content=task_description))

        response = await self.provider.chat_with_retry(messages)
        return response.content

    async def decompose_goal(self, goal: str, available_agents: list[str]) -> list[dict]:
        """Decompose a goal into tasks (primarily used by CEO agent).

        Returns list of dicts: [{"title": "...", "description": "...", "assigned_to": "role_key", "depends_on": []}]
        """
        system_prompt = self.role.system_prompt.replace("{goal}", goal)

        prompt = f"""You are decomposing the following goal into actionable tasks for your team.

Goal: {goal}

Available team members (by role_key): {json.dumps(available_agents)}

Break this goal into 3-8 concrete, actionable tasks. Assign each task to the most appropriate team member.

Respond ONLY with a JSON array (no markdown, no explanation):
[
  {{"title": "Task title", "description": "Detailed description", "assigned_to": "role_key", "depends_on": []}}
]

Rules:
- Each task must be specific and actionable
- assigned_to must be one of the available role_keys
- depends_on is a list of task indices (0-based) that must complete before this task
- Order tasks logically
- Do not assign tasks to yourself (ceo) unless it's a review/decision task"""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self.provider.chat_with_retry(messages, temperature=0.3)

        # Parse JSON response
        try:
            text = response.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            tasks = json.loads(text)
            return tasks
        except (json.JSONDecodeError, IndexError):
            logger.error(f"Failed to parse goal decomposition: {response.content}")
            return [{"title": "Execute goal", "description": goal, "assigned_to": available_agents[0] if available_agents else "ceo", "depends_on": []}]

    async def evaluate_completion(self, goal: str, task_results: list[dict]) -> dict:
        """Evaluate if the goal is complete (used by CEO agent).

        Returns: {"complete": bool, "summary": "...", "next_steps": [...]}
        """
        results_text = "\n".join(
            f"- Task: {r['title']} (by {r['assigned_to']}): {r.get('result', 'No result')[:500]}"
            for r in task_results
        )

        prompt = f"""Evaluate if the following goal has been achieved based on the task results.

Goal: {goal}

Task Results:
{results_text}

Respond ONLY with JSON (no markdown):
{{"complete": true/false, "summary": "Brief summary of what was accomplished", "next_steps": ["step1", "step2"] }}

If complete is true, next_steps should be empty.
If complete is false, list what still needs to be done."""

        system_prompt = self.role.system_prompt.replace("{goal}", goal)
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=prompt),
        ]

        response = await self.provider.chat_with_retry(messages, temperature=0.2)

        try:
            text = response.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {"complete": False, "summary": "Unable to evaluate", "next_steps": ["Review results manually"]}
