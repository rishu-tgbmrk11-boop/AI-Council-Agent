# core/agent.py
import time
from dotenv import load_dotenv
import aisuite as ai
from core.message import Message
from core.board import MessageBoard

# core/agent.py
import time
from dotenv import load_dotenv
import aisuite as ai
from core.message import Message
from core.board import MessageBoard

# ─── MONKEY PATCH: Fix Groq reasoning_content 400 error ───
# Groq's strict API rejects the 'reasoning_content' field on assistant
# messages with HTTP 400. This patch strips it before sending.
from aisuite.providers.groq_provider import GroqMessageConverter
from aisuite.providers.openai_provider import OpenAICompliantMessageConverter

class _PatchedGroqMessageConverter(OpenAICompliantMessageConverter):
    @classmethod
    def convert_request(cls, messages):
        transformed = OpenAICompliantMessageConverter.convert_request(messages)
        for msg in transformed:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                msg.pop("reasoning_content", None)
        return transformed

GroqMessageConverter.convert_request = _PatchedGroqMessageConverter.convert_request
# ─── END MONKEY PATCH ───

load_dotenv()

load_dotenv()


class Agent:
    def __init__(self, name: str, model: str, persona: str, board: MessageBoard,
                 fallback_model: str = None, tools: list = None):
        self.name = name
        self.model = model
        self.fallback_model = fallback_model
        self.persona = persona
        self.board = board
        self.tools = tools or []
        self.client = ai.Client()
        self._current_model = model   # tracks which model is active
        self.agent = self._build_agent(model)

    def _build_agent(self, model: str):
        """Build an aisuite Agent with the given model + tools."""
        return ai.Agent(
            name=self.name,
            model=model,
            instructions=self._system_prompt(),
            tools=self.tools,
        )

    def _system_prompt(self) -> str:
        tool_hint = ""
        if self.tools:
            names = ", ".join(t.__name__ for t in self.tools)
            tool_hint = (
    f"\n\nYou have access to these tools: {names}. "
    f"Use each tool AT MOST ONCE per turn. "
    f"After calling a tool, immediately write your final text response using the results. "
    f"Do NOT call the same tool multiple times. "
    f"Do NOT make up numbers — but if a tool fails, work with what you have."
)

        return f"""You are {self.name}.
Your role: {self.persona}{tool_hint}

Keep responses substantive but focused (3-4 sentences).
- Directly respond to specific points made by other agents (name them).
- If you disagree, say so and explain why.
- If you agree, extend the idea rather than repeating it."""

    def _run(self, prompt: str, use_fallback: bool = False) -> str:
        """Run the agent with the primary or fallback model."""
        target_model = self.fallback_model if use_fallback else self.model

        if target_model != self._current_model:
            self.agent = self._build_agent(target_model)
            self._current_model = target_model

        result = ai.Runner.run_sync(
            self.agent,
            prompt,
            client=self.client,
            max_turns=2,   # ← HARD CAP: 1 tool call + 1 final text
        )

        # 1. Prefer the explicit final output
        if result.final_output and result.final_output.strip():
            return result.final_output

        # 2. Fall back to the last assistant message with string content
        for msg in reversed(result.messages):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if role == "assistant" and isinstance(content, str) and content.strip():
                return content.strip()

        # 3. Nothing usable
        return ""

    def think(self, goal: str, context: str,
              current_step: int = 1, total_steps: int = 9) -> str:
        # ─── Step-awareness instruction ───
        if current_step <= 3:
            step_hint = (
                "This is early in the debate. State your initial position clearly. "
                "If you need external facts or calculations, use your tools now."
            )
        else:
            step_hint = (
                "The debate is well underway. Build directly on what others said. "
                "Name the agent you're responding to. Do NOT repeat your earlier points. "
                "If someone made a factual claim you can verify, use your tools."
            )

        prompt = f"""GOAL:
{goal}

RECENT DEBATE:
{context}

{step_hint}

Provide your contribution now."""

        # ─── Try primary model, retry on transient errors or empty responses, fall back if needed ───
        for attempt in range(3):
            try:
                result = self._run(prompt, use_fallback=False)

                # Treat empty output as a failure → retry or fall back
                if result and result.strip():
                    return result

                print(f"⚠️ [{self.name}] empty response, retrying (attempt {attempt + 1})")
                if attempt < 2:
                    time.sleep(2)
                    continue
                raise ValueError("empty response after retries")

            except Exception as e:
                err = str(e)
                is_transient = any(
                    code in err for code in ["503", "429", "UNAVAILABLE", "overloaded", "empty"]
                )
                if is_transient and attempt < 2:
                    wait = 2 ** attempt
                    print(f"⏳ [{self.name}] {err[:60]}... retrying in {wait}s")
                    time.sleep(wait)
                    continue

                # Retries exhausted → try fallback
                if self.fallback_model:
                    print(f"⚠️ [{self.name}] falling back to {self.fallback_model}")
                    try:
                        fallback_result = self._run(prompt, use_fallback=True)
                        if fallback_result and fallback_result.strip():
                            return fallback_result + \
                                   f"\n\n_(Note: primary model unavailable, responded via {self.fallback_model})_"
                        return f"(error: fallback also returned empty)"
                    except Exception as e2:
                        return f"(error: both primary and fallback failed: {str(e2)[:80]})"

                return f"(error: {err[:100]})"

            
    def act(self, goal: str, current_step: int = 1, total_steps: int = 9):
        context = self.board.get_context_string(n=6)
        thought = self.think(goal, context, current_step, total_steps)
        message = Message(sender=self.name, content=thought)
        self.board.post(message)