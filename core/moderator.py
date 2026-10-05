# core/moderator.py
from dotenv import load_dotenv
import aisuite as ai
from core.board import MessageBoard

load_dotenv()


class Moderator:
    """
    The Moderator decides who speaks next. It does NOT participate in the debate.
    Uses a fast model (Groq) to minimize latency.
    """
    def __init__(self, model: str = "groq:qwen/qwen3.8-27b"):
        self.model = model
        self.client = ai.Client()

    def next_speaker(self, goal: str, board: MessageBoard,
                     participants: list, max_steps: int = 12) -> str:
        """
        Returns the name of the next agent to speak, or 'END' to stop the debate.
        """
        transcript = "\n\n".join(
            f"[{m.sender}]: {m.content}"
            for m in board.get_all()
        )

        # Count how many times each agent has spoken
        speaker_counts = {name: 0 for name in participants}
        for m in board.get_all():
            if m.sender in speaker_counts:
                speaker_counts[m.sender] += 1

        counts_str = ", ".join(f"{name}: {count}" for name, count in speaker_counts.items())

        prompt = f"""You are a neutral moderator of a multi-agent debate. You do NOT debate. You only decide who speaks next.

GOAL OF THE DEBATE:
{goal}

PARTICIPANTS: {", ".join(participants)}
SPEAK COUNT SO FAR: {counts_str}
TOTAL MESSAGES SO FAR: {board.length()} (max allowed: {max_steps})

FULL DEBATE TRANSCRIPT:
{transcript}

Your job:
1. Decide who should speak NEXT based on the flow of the conversation.
2. Consider:
   - Who hasn't spoken yet? (fairness)
   - Who would add the most value right now? (relevance)
   - Has consensus been reached? If yes, is it time to END?
   - Are two agents stuck in a loop? If yes, force a different speaker.
3. If the debate has run its course AND the synthesizer has produced a strong summary, respond with 'END'.
4. Do NOT let the same agent speak more than 3 times in a row.

Return ONLY the name of the next speaker (or 'END'). No explanation. No other text.
Valid responses: {", ".join(participants)}, or END
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
            )
            decision = (response.choices[0].message.content or "").strip()

            # Sanitize: must be a participant name or END
            for name in participants:
                if name.lower() in decision.lower():
                    return name
            if "end" in decision.lower():
                return "END"
            # Fallback: pick whoever spoke least
            return min(speaker_counts, key=speaker_counts.get)

        except Exception as e:
            print(f"⚠️ Moderator failed ({str(e)[:60]}), falling back to round-robin")
            return min(speaker_counts, key=speaker_counts.get)