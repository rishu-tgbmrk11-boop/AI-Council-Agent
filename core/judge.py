# core/judge.py
import json
import re
from dotenv import load_dotenv
import aisuite as ai
from core.board import MessageBoard

load_dotenv()


class Judge:
    def __init__(self,
                 model: str = "groq:qwen/qwen3.8-27b",
                 fallback_model: str = "groq:openai/gpt-oss-120b"):
        self.model = model
        self.fallback_model = fallback_model
        self.client = ai.Client()

    def _call_judge(self, model: str, prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
        )
        content = response.choices[0].message.content or ""
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        return {"error": "Could not parse judge response", "raw": content[:300]}

    def evaluate(self, goal: str, board: MessageBoard) -> dict:
        # ─── Build transcript ───
        transcript = "\n\n".join(
            f"[{m.sender}]: {m.content}"
            for m in board.get_all()
        )

        # ─── Build per-agent contributions ───
        agent_names = set(
            m.sender for m in board.get_all()
            if m.sender not in ("User", "Moderator")
        )
        agent_block = ""
        for name in agent_names:
            msgs = [m for m in board.get_all() if m.sender == name]
            if msgs:
                combined = "\n".join(f"- {m.content}" for m in msgs)
                agent_block += f"### {name}'s CONTRIBUTIONS:\n{combined}\n\n"

        prompt = f"""You are an impartial judge evaluating a multi-model AI debate. Your job is NOT to pick a winner. Your job is to score the PROCESS and the INTEGRATION.

GOAL THE COUNCIL WAS GIVEN:
{goal}

═══════════════════════════════════════════
FULL DEBATE TRANSCRIPT:
═══════════════════════════════════════════
{transcript}

═══════════════════════════════════════════
PER-AGENT CONTRIBUTIONS:
═══════════════════════════════════════════
{agent_block}

═══════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════
Score the debate on the following dimensions (each 1-10). Be critical: 10 means flawless and should be rare.

1. REASONING_QUALITY
   Did the agents reason rigorously? Are arguments logically sound?

2. EVIDENCE_GROUNDING
   Were factual claims backed by tools (web search, calculations), or simply asserted?
   Penalize unsupported numbers and unverified claims.

3. PERSPECTIVE_INTEGRATION
   Did the final synthesis incorporate key points from ALL agents?
   A synthesis that ignores a whole agent's contribution scores LOW here.
   A synthesis that meaningfully combines multiple perspectives scores HIGH.

4. DISAGREEMENT_RESOLUTION
   When agents disagreed, was the conflict addressed, or was it smoothed over?
   A synthesis that avoids disagreement scores LOW.
   A synthesis that explicitly resolves the disagreement scores HIGH.

5. HALLUCINATION_ABSENCE
   Did any agent fabricate facts, numbers, or citations?
   Fewer fabrications = higher score. Any obvious fabrication caps this at 5.

6. PROCESS_ENGAGEMENT
   Did agents respond to EACH OTHER by name? Did they build on prior points, or just repeat?
   Agents talking past each other = LOW. Real back-and-forth = HIGH.

7. CONVERGENCE_QUALITY
   Did the debate converge on a conclusion for good reasons (evidence, logic), or did it end prematurely?
   Premature END with no synthesis = LOW.

8. OVERALL_SCORE
   Single overall quality number (1-10), weighting the debate as a whole — not just the final answer.

VERDICT: 2-3 sentences of honest assessment. What worked, what didn't, what could improve next time.

Return ONLY valid JSON in this exact format, no other text:
{{
  "reasoning_quality": <number>,
  "evidence_grounding": <number>,
  "perspective_integration": <number>,
  "disagreement_resolution": <number>,
  "hallucination_absence": <number>,
  "process_engagement": <number>,
  "convergence_quality": <number>,
  "overall_score": <number>,
  "verdict": "<2-3 sentences>"
}}
"""

        try:
            return self._call_judge(self.model, prompt)
        except Exception as e:
            print(f"⚠️ Judge primary failed ({str(e)[:60]}), falling back to {self.fallback_model}")
            try:
                return self._call_judge(self.fallback_model, prompt)
            except Exception as e2:
                return {"error": f"Both judge models failed: {str(e2)[:150]}"}