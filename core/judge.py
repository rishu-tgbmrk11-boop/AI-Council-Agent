# core/judge.py
import json
import re
from dotenv import load_dotenv
import aisuite as ai
from core.board import MessageBoard

load_dotenv()


class Judge:
    def __init__(self,
                 model: str = "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
                 fallback_model: str = "groq:qwen/qwen3.8-27b"):
        self.model = model
        self.fallback_model = fallback_model
        self.client = ai.Client()

    def _call_judge(self, model: str, prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
        content = response.choices[0].message.content or ""
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        return {"error": "Could not parse judge response", "raw": content[:300]}

    def evaluate(self, goal: str, board: MessageBoard) -> dict:
        # ─── Build transcript ───
        transcript = "\n\n".join(
            f"[{m.sender}] ({m.message_type}): {m.content}"
            for m in board.get_all()
        )

        # ─── Extract individual agent positions (their last message) ───
        agent_names = set(m.sender for m in board.get_all() if m.sender != "User")
        individual_answers = {}
        for name in agent_names:
            agent_msgs = [m for m in board.get_all() if m.sender == name]
            if agent_msgs:
                individual_answers[name] = agent_msgs[-1].content

        synth_msgs = [m for m in board.get_all() if m.sender == "The Synthesizer"]
        final_synthesis = synth_msgs[-1].content if synth_msgs else "(none)"

        # ─── Format individual answers for the prompt ───
        individual_block = "\n\n".join(
            f"### {name}'s FINAL POSITION:\n{content}"
            for name, content in individual_answers.items()
        )

        prompt = f"""You are an impartial judge evaluating a multi-model AI debate.

GOAL THE COUNCIL WAS GIVEN:
{goal}

═══════════════════════════════════════════
FULL DEBATE TRANSCRIPT:
═══════════════════════════════════════════
{transcript}

═══════════════════════════════════════════
INDIVIDUAL AGENTS' FINAL POSITIONS:
═══════════════════════════════════════════
{individual_block}

═══════════════════════════════════════════
FINAL SYNTHESIS (from The Synthesizer):
═══════════════════════════════════════════
{final_synthesis}

═══════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════
1. Score each agent's individual final position on a 1-10 scale for QUALITY.
2. Score the FINAL SYNTHESIS on a 1-10 scale.
3. Compare: Is the synthesis BETTER than the best individual answer? By how much?
   - If yes, explain what the synthesis added that no single agent produced.
   - If no, explain what was lost when merging the perspectives.
4. Score the debate itself on these dimensions (1-10):
   - REASONING_QUALITY
   - PERSPECTIVE_DIVERSITY
   - DEPTH_OF_DEBATE (did they build on each other, or repeat?)

Return ONLY valid JSON in this exact format, no other text:
{{
  "individual_scores": {{
    "The Logician": <number>,
    "The Analyst": <number>,
    "The Synthesizer": <number>
  }},
  "synthesis_score": <number>,
  "best_individual": "<agent name>",
  "best_individual_score": <number>,
  "synthesis_delta": <number>,
  "synthesis_verdict": "<2-3 sentences: did the council add value beyond the best single agent?>",
  "reasoning_quality": <number>,
  "perspective_diversity": <number>,
  "depth_of_debate": <number>,
  "final_answer_quality": <number>,
  "overall_score": <number>,
  "verdict": "<2-3 sentences of honest overall assessment>"
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