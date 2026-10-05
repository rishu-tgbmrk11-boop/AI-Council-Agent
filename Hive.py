# hive.py
from core.board import MessageBoard
from core.message import Message
from core.agent import Agent
from core.moderator import Moderator
from core.judge import Judge
from tools.web_search import web_search
from tools.python_repl import python_repl


# ─────────────────────────────────────────────
# THE COUNCIL — each agent gets its own tools
# ─────────────────────────────────────────────
COUNCIL = [
    {
        "name": "The Logician",
        "model": "groq:openai/gpt-oss-120b",
        "persona": (
            "You are a rigorous analytical reasoner. You decompose problems into steps, "
            "spot logical flaws, and use calculations to verify claims. "
            "When someone quotes a number, verify it with python_repl."
        ),
        "fallback": "groq:qwen/qwen3.8-27b",
        "tools": [python_repl],           # calculations only
    },
    {
        "name": "The Analyst",
        "model": "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
        "persona": (
    "You are a creative lateral thinker. You bring current facts, statistics, and "
    "external context. When you need pricing or recent data, call web_search ONCE. "
    "If the first result gives you a partial answer, use what you have — do NOT "
    "search again. Then immediately write your argument."
),
        "fallback": "groq:openai/gpt-oss-120b",
        "tools": [web_search],            # web search only
    },
    {
        "name": "The Synthesizer",
        "model": "groq:qwen/qwen3.8-27b",
        "persona": (
            "You are an integrative thinker. You listen to all sides, find common ground, "
            "and produce the final synthesized answer. You do not make up facts — you "
            "integrate what the other agents have established."
        ),
        "fallback": "groq:openai/gpt-oss-120b",
        "tools": [],                      # pure synthesis, no tools
    },
]


class HIVE:
    def __init__(self, goal: str, max_steps: int = 9):
        self.goal = goal
        self.max_steps = max_steps          # total agent turns
        self.board = MessageBoard()
        self.agents = {
            c["name"]: Agent(
                name=c["name"],
                model=c["model"],
                persona=c["persona"],
                board=self.board,
                fallback_model=c.get("fallback"),
                tools=c.get("tools", []),    # ← pass tools
            )
            for c in COUNCIL
        }
        self.participants = list(self.agents.keys())
        self.moderator = Moderator()

    def run(self):
        # Post the goal
        self.board.post(
            Message(sender="User", content=self.goal, role="user", message_type="goal")
        )

        step = 0
        while step < self.max_steps:
            step += 1
            print(f"\n{'=' * 60}")
            print(f"STEP {step} / {self.max_steps}")
            print(f"{'=' * 60}")

            speaker = self.moderator.next_speaker(
                self.goal, self.board, self.participants, max_steps=self.max_steps
            )
            print(f"🎙️ Moderator chose: {speaker}")

            if speaker == "END":
                print("🛑 Moderator ended the debate.")
                break

            self.agents[speaker].act(
                self.goal,
                current_step=step,
                total_steps=self.max_steps,
            )

        # ─── Final board state ───
        print(f"\n{'=' * 60}")
        print("FINAL BOARD STATE")
        print(f"{'=' * 60}")
        for msg in self.board.get_all():
            print(msg)

        # ─── Judge ───
        print(f"\n{'=' * 60}")
        print("JUDGE'S VERDICT")
        print(f"{'=' * 60}")
        judge = Judge()
        scores = judge.evaluate(self.goal, self.board)

        if "error" in scores:
            print(f"❌ Judge failed: {scores['error']}")
        else:
            print(f"🧠 Reasoning:          {scores.get('reasoning_quality', 0)}/10")
            print(f"🎨 Perspective:        {scores.get('perspective_diversity', 0)}/10")
            print(f"🔍 Depth:              {scores.get('depth_of_debate', 0)}/10")
            print(f"🏆 Final Answer:       {scores.get('final_answer_quality', 0)}/10")
            print(f"\n⭐ OVERALL: {scores.get('overall_score', 0)}/10")
            print(f"\n📝 Verdict: {scores.get('verdict', 'N/A')}")


if __name__ == "__main__":
    goal = input("Enter a goal for the HIVE: ").strip()
    if not goal:
        goal = "Which is cheapest for a startup processing 50 million tokens per month in 2026: GPT-OSS, Gemini Flash, or Llama 3.3?"
    hive = HIVE(goal=goal, max_steps=9)
    hive.run()