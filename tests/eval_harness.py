# tests/eval_harness.py
import sys
import os
import json
import time
import sqlite3
from datetime import datetime

# Allow imports from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.board import MessageBoard
from core.message import Message
from core.agent import Agent
from core.moderator import Moderator
from core.judge import Judge
from tools.web_search import web_search
from tools.python_repl import python_repl


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
COUNCIL = [
    {
        "name": "The Logician",
        "model": "groq:openai/gpt-oss-120b",
        "persona": (
            "You are a rigorous analytical reasoner. You decompose problems into steps, "
            "spot logical flaws, and use calculations to verify claims. "
            "When someone quotes a number, verify it with python_repl. "
            "Actively identify the WEAKEST claim made by another agent and challenge it. "
            "Do not agree quickly."
        ),
        "fallback": "groq:qwen/qwen3.8-27b",
        "tools": [python_repl],
    },
    {
        "name": "The Analyst",
        "model": "groq:qwen/qwen3.8-27b",
        "persona": (
            "You are a creative lateral thinker. You bring current facts, statistics, and "
            "external context. When you need pricing or recent data, call web_search ONCE. "
            "If the first result gives you a partial answer, use what you have — do NOT "
            "search again. If another agent's claim cannot be verified, say so. "
            "Push back on unverified numbers."
        ),
        "fallback": "groq:openai/gpt-oss-20b",
        "tools": [web_search],
    },
    {
        "name": "The Synthesizer",
        "model": "groq:openai/gpt-oss-20b",
        "persona": (
            "You are an integrative thinker. Read every agent's contribution carefully. "
            "Your job is to produce the STRONGEST possible answer — not a compromise. "
            "If one agent made a clearly superior argument, adopt their position entirely. "
            "If multiple agents had valid points, combine them WITHOUT diluting specifics. "
            "Do NOT soften claims to please everyone. Do NOT average positions. "
            "Quote exact numbers and specifics. Never say 'both perspectives have merit'."
        ),
        "fallback": "groq:openai/gpt-oss-120b",
        "tools": [],
    },
]

MAX_STEPS = 6
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "eval_results.db"
)


# ─────────────────────────────────────────────
# DATABASE — new 8-dimension schema
# ─────────────────────────────────────────────
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_group TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            category TEXT,
            difficulty TEXT,
            goal TEXT,
            timestamp TEXT,
            steps_used INTEGER,
            overall_score REAL,
            reasoning_quality REAL,
            evidence_grounding REAL,
            perspective_integration REAL,
            disagreement_resolution REAL,
            hallucination_absence REAL,
            process_engagement REAL,
            convergence_quality REAL,
            verdict TEXT,
            judge_raw TEXT,
            transcript TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_run(run_group, goal_meta, board, judge_scores, steps_used, transcript):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO runs (
            run_group, goal_id, category, difficulty, goal, timestamp, steps_used,
            overall_score, reasoning_quality, evidence_grounding,
            perspective_integration, disagreement_resolution, hallucination_absence,
            process_engagement, convergence_quality, verdict, judge_raw, transcript
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_group,
        goal_meta["id"],
        goal_meta.get("category", ""),
        goal_meta.get("difficulty", ""),
        goal_meta["goal"],
        datetime.now().isoformat(),
        steps_used,
        judge_scores.get("overall_score"),
        judge_scores.get("reasoning_quality"),
        judge_scores.get("evidence_grounding"),
        judge_scores.get("perspective_integration"),
        judge_scores.get("disagreement_resolution"),
        judge_scores.get("hallucination_absence"),
        judge_scores.get("process_engagement"),
        judge_scores.get("convergence_quality"),
        judge_scores.get("verdict"),
        json.dumps(judge_scores),
        transcript,
    ))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# DEBATE RUNNER (headless)
# ─────────────────────────────────────────────
def run_debate(goal):
    board = MessageBoard()
    agents = {
        c["name"]: Agent(
            name=c["name"], model=c["model"], persona=c["persona"],
            board=board, fallback_model=c.get("fallback"), tools=c.get("tools", []),
        )
        for c in COUNCIL
    }
    participants = list(agents.keys())
    moderator = Moderator()

    board.post(Message(sender="User", content=goal, role="user", message_type="goal"))

    step = 0
    while step < MAX_STEPS:
        step += 1
        speaker = moderator.next_speaker(goal, board, participants, max_steps=MAX_STEPS)
        if speaker == "END":
            break
        try:
            agents[speaker].act(goal, current_step=step, total_steps=MAX_STEPS)
        except Exception as e:
            print(f"    ⚠️ Agent {speaker} failed: {str(e)[:80]}")

    return board, step


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    init_db()
    run_group = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    goals_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "eval_goals.json"
    )
    with open(goals_file) as f:
        data = json.load(f)

    goals = data["goals"]
    print(f"\n{'='*70}")
    print(f"HIVE EVAL HARNESS — {run_group}")
    print(f"Running {len(goals)} goals")
    print(f"{'='*70}\n")

    results = []
    for i, goal_meta in enumerate(goals, 1):
        print(f"\n[{i}/{len(goals)}] {goal_meta['id']} ({goal_meta['difficulty']})")
        print(f"    Goal: {goal_meta['goal'][:80]}...")

        # Rate-limit cooldown between debates
        if i > 1:
            print("    ⏳ Cooling down 45s to respect rate limits...")
            time.sleep(45)

        try:
            board, steps_used = run_debate(goal_meta["goal"])
            print(f"    ✓ Debate complete in {steps_used} steps")

            judge = Judge()
            scores = judge.evaluate(goal_meta["goal"], board)

            if "error" in scores:
                print(f"    ❌ Judge failed: {scores['error'][:100]}")
                continue

            transcript = "\n\n".join(
                f"[{m.sender}]: {m.content}" for m in board.get_all()
            )
            save_run(run_group, goal_meta, board, scores, steps_used, transcript)

            overall = scores.get("overall_score", 0)
            pi = scores.get("perspective_integration", 0)
            ee = scores.get("evidence_grounding", 0)
            print(f"    ✓ Judge: overall={overall}/10, integration={pi}/10, evidence={ee}/10")
            results.append({
                "goal_id": goal_meta["id"],
                "overall": overall,
                "integration": pi,
                "evidence": ee,
            })

        except Exception as e:
            print(f"    ❌ Debate failed: {str(e)[:120]}")
            continue

    # ── Summary
    print(f"\n{'='*70}")
    print(f"EVAL COMPLETE — {len(results)}/{len(goals)} goals scored")
    print(f"{'='*70}")
    if results:
        avg_overall = sum(r["overall"] for r in results) / len(results)
        avg_integration = sum(r["integration"] for r in results) / len(results)
        avg_evidence = sum(r["evidence"] for r in results) / len(results)
        print(f"  Average overall score:        {avg_overall:.2f}/10")
        print(f"  Average perspective integr.:  {avg_integration:.2f}/10")
        print(f"  Average evidence grounding:   {avg_evidence:.2f}/10")
        print(f"\n  Run group: {run_group}")
        print(f"  Results DB: {DB_PATH}")
        print(f"\n  Analyze: python tests/eval_analysis.py {run_group}\n")


if __name__ == "__main__":
    main()