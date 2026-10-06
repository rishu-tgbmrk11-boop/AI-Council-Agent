# ui/app.py
import streamlit as st
import sys
import os
import time
import json
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
# PAGE CONFIG + CUSTOM CSS
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="HIVE · Multi-Model Debate",
    page_icon="🐝",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    .hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2d3561;
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 24px;
    }
    .hero-title {
        font-size: 38px;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #FFD166, #FF6B35, #F7B801);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero-subtitle {
        color: #8892b0;
        font-size: 15px;
        margin-top: 6px;
    }

    .agent-card {
        padding: 12px 14px;
        border-radius: 10px;
        margin-bottom: 10px;
        transition: all 0.2s ease;
    }
    .agent-card:hover { transform: translateX(2px); }
    .agent-card .agent-name {
        font-size: 15px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .agent-card .agent-meta {
        font-size: 11px;
        color: #8892b0;
        margin-top: 4px;
    }
    .agent-card .agent-tools {
        font-size: 10px;
        color: #6c7a89;
        margin-top: 3px;
    }
    .agent-card .agent-status {
        font-size: 10px;
        font-weight: 600;
        margin-top: 6px;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.3); }
    }
    .status-speaking { animation: pulse 1.2s infinite; }

    .step-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 28px 0 14px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #2d3561;
    }
    .step-number {
        background: #2d3561;
        color: #FFD166;
        font-weight: 700;
        font-size: 13px;
        padding: 4px 12px;
        border-radius: 20px;
    }
    .step-moderator {
        color: #8892b0;
        font-size: 13px;
    }

    .msg-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }
    .msg-name {
        font-weight: 700;
        font-size: 15px;
    }
    .msg-meta {
        color: #6c7a89;
        font-size: 12px;
    }

    div[data-testid="stMetric"] {
        background: #16213e;
        border: 1px solid #2d3561;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricLabel"] { color: #8892b0 !important; }

    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #16213e;
        border-radius: 8px;
        padding: 8px 20px;
        color: #8892b0;
    }
    .stTabs [aria-selected="true"] {
        background: #2d3561 !important;
        color: #FFD166 !important;
    }

    .rubric-card {
        padding: 14px 18px;
        border-radius: 10px;
        background: #16213e;
        border: 1px solid #2d3561;
        margin-bottom: 12px;
    }
    .rubric-card .rubric-title {
        font-weight: 600;
        color: #FFD166;
        font-size: 13px;
        margin-bottom: 6px;
    }
    .rubric-card .rubric-desc {
        color: #8892b0;
        font-size: 11px;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# THE COUNCIL
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
        "tool_names": ["python_repl"],
        "icon": "🧠",
        "color": "#10A37F",
        "provider": "Groq",
        "model_label": "GPT-OSS 120B",
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
        "tool_names": ["web_search"],
        "icon": "🎯",
        "color": "#FF6B35",
        "provider": "Groq",
        "model_label": "Qwen 3.8 27B",
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
        "tool_names": [],
        "icon": "🦙",
        "color": "#7B61FF",
        "provider": "Groq",
        "model_label": "GPT-OSS 20B",
    },
]

def agent_config(name: str):
    return next((a for a in COUNCIL if a["name"] == name), None)


# ─────────────────────────────────────────────
# RUBRIC — display metadata for the new Judge dimensions
# ─────────────────────────────────────────────
RUBRIC = [
    ("reasoning_quality",       "🧠 Reasoning Quality",       "Are arguments logically sound and rigorous?"),
    ("evidence_grounding",      "📚 Evidence Grounding",      "Are factual claims backed by tools, or just asserted?"),
    ("perspective_integration", "🧬 Perspective Integration", "Did the synthesis cover ALL agents' key points?"),
    ("disagreement_resolution", "⚖️ Disagreement Resolution", "Were conflicts addressed, or smoothed over?"),
    ("hallucination_absence",   "🚫 Hallucination Absence",   "Did anyone fabricate facts or numbers?"),
    ("process_engagement",      "💬 Process Engagement",      "Did agents respond to each other by name?"),
    ("convergence_quality",     "🎯 Convergence Quality",     "Did the debate end for good reasons?"),
    ("overall_score",           "🏆 Overall Score",           "Holistic quality of the debate."),
]


def save_debate_to_db(goal, board, scores, steps_completed):
    """Persist a UI debate to the same DB the eval harness writes to."""
    try:
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "eval_results.db"
        )
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # New schema with 8 rubric dimensions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_group TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                category TEXT, difficulty TEXT, goal TEXT, timestamp TEXT,
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
        transcript = "\n\n".join(f"[{m.sender}]: {m.content}" for m in board.get_all())
        cur.execute("""
            INSERT INTO runs (
                run_group, goal_id, category, difficulty, goal, timestamp, steps_used,
                overall_score, reasoning_quality, evidence_grounding,
                perspective_integration, disagreement_resolution, hallucination_absence,
                process_engagement, convergence_quality, verdict, judge_raw, transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ui_live",
            f"ui_{datetime.now().strftime('%H%M%S')}",
            "ad_hoc", "live",
            goal,
            datetime.now().isoformat(),
            steps_completed,
            scores.get("overall_score"),
            scores.get("reasoning_quality"),
            scores.get("evidence_grounding"),
            scores.get("perspective_integration"),
            scores.get("disagreement_resolution"),
            scores.get("hallucination_absence"),
            scores.get("process_engagement"),
            scores.get("convergence_quality"),
            scores.get("verdict"),
            json.dumps(scores),
            transcript,
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.warning(f"Could not save debate to eval DB: {e}")
        return False


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
defaults = {
    "messages": [],
    "goal": "",
    "steps_completed": 0,
    "moderator_log": [],
    "debate_done": False,
    "judge_scores": None,
    "currently_speaking": None,
    "started_at": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────────
# HERO HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1 class="hero-title">🐝 HIVE</h1>
    <p class="hero-subtitle">
        A council of three AI architectures debating under a dynamic moderator,
        evaluated on process quality across 8 dimensions.
    </p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Debate Setup")

    st.session_state.goal = st.text_area(
        "🎯 Goal",
        value=st.session_state.goal or "Which is cheapest for a startup processing 50M tokens/month in 2026: GPT-OSS, Gemini Flash, or Llama 3.3?",
        height=90,
        label_visibility="collapsed",
        placeholder="Enter a goal for the council...",
    )

    col_a, col_b = st.columns([2, 1])
    with col_a:
        max_steps = st.slider("Max steps", 4, 10, 6, label_visibility="collapsed")
    with col_b:
        st.caption(f"≤ {max_steps} turns")

    start = st.button("🚀 Start Debate", use_container_width=True, type="primary")

    st.divider()
    st.markdown("### 🎭 The Council")

    for agent in COUNCIL:
        count = sum(1 for m in st.session_state.messages if m.sender == agent["name"])
        speaking = st.session_state.currently_speaking == agent["name"]

        if speaking:
            status_html = f'<span class="status-speaking" style="color:{agent["color"]};">● thinking…</span>'
            border_style = f"2px solid {agent['color']}"
            bg = f"linear-gradient(90deg, {agent['color']}22 0%, #16213e 100%)"
        elif count > 0:
            status_html = f'<span style="color:#4ade80;">✓ {count} message{"s" if count != 1 else ""}</span>'
            border_style = f"1px solid {agent['color']}55"
            bg = "#16213e"
        else:
            status_html = '<span style="color:#6c7a89;">○ idle</span>'
            border_style = "1px solid #2d3561"
            bg = "#0f1829"

        tools_str = ", ".join(agent.get("tool_names", [])) or "—"

        st.markdown(f"""
        <div class="agent-card" style="background:{bg}; border:{border_style}; border-left:4px solid {agent['color']};">
            <div class="agent-name">
                <span>{agent['icon']} {agent['name']}</span>
            </div>
            <div class="agent-meta">{agent['provider']} · {agent['model_label']}</div>
            <div class="agent-tools">🛠️ {tools_str}</div>
            <div class="agent-status">{status_html}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    m1, m2 = st.columns(2)
    m1.metric("Messages", len(st.session_state.messages))
    m2.metric("Steps", st.session_state.steps_completed)

    if st.session_state.moderator_log:
        with st.expander("🎙️ Moderator Log", expanded=False):
            for entry in st.session_state.moderator_log:
                st.caption(entry)

    if st.session_state.messages:
        if st.button("🗑️ Reset Debate", use_container_width=True):
            for key in defaults:
                st.session_state[key] = defaults[key]
            st.rerun()

# ─────────────────────────────────────────────
# MAIN AREA — TABS
# ─────────────────────────────────────────────
tab_debate, tab_judge, tab_evals, tab_raw = st.tabs(
    ["💬 Debate", "⚖️ Judge", "📊 Evals", "📄 Raw Transcript"]
)

# ─────────────────────────────────────────────
# TAB 1: DEBATE
# ─────────────────────────────────────────────
with tab_debate:
    if not st.session_state.messages and not start:
        st.info("👈 Set a goal in the sidebar and click **Start Debate** to begin.")

    if not start and st.session_state.messages:
        for msg in st.session_state.messages:
            if msg.sender == "User":
                with st.chat_message("user"):
                    st.markdown(f"**🎯 Goal:** {msg.content}")
            elif msg.sender == "Moderator":
                st.markdown(f"""
                <div class="step-header">
                    <span class="step-moderator">{msg.content}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                cfg = agent_config(msg.sender)
                if not cfg:
                    continue
                with st.chat_message("assistant", avatar=cfg["icon"]):
                    st.markdown(
                        f'<div class="msg-header">'
                        f'<span class="msg-name" style="color:{cfg["color"]};">{cfg["name"]}</span>'
                        f'<span class="msg-meta">· {cfg["provider"]} · {cfg["model_label"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(msg.content)

    if start:
        st.session_state.messages = []
        st.session_state.steps_completed = 0
        st.session_state.moderator_log = []
        st.session_state.debate_done = False
        st.session_state.judge_scores = None
        st.session_state.started_at = time.time()

        board = MessageBoard()
        agents = {
            c["name"]: Agent(
                name=c["name"], model=c["model"], persona=c["persona"],
                board=board, fallback_model=c.get("fallback"),
                tools=c.get("tools", []),
            )
            for c in COUNCIL
        }
        participants = list(agents.keys())
        moderator = Moderator()

        goal_msg = Message(sender="User", content=st.session_state.goal, role="user", message_type="goal")
        board.post(goal_msg)
        st.session_state.messages.append(goal_msg)
        with st.chat_message("user"):
            st.markdown(f"**🎯 Goal:** {st.session_state.goal}")

        progress_bar = st.progress(0.0, text="Starting debate...")

        step = 0
        while step < max_steps:
            step += 1
            progress_bar.progress(step / max_steps, text=f"Step {step}/{max_steps}")

            with st.spinner("🎙️ Moderator is deciding..."):
                speaker = moderator.next_speaker(
                    st.session_state.goal, board, participants, max_steps=max_steps
                )

            log_entry = f"Step {step}: → {speaker}"
            st.session_state.moderator_log.append(log_entry)

            st.markdown(f"""
            <div class="step-header">
                <span class="step-number">Step {step}/{max_steps}</span>
                <span class="step-moderator">🎙️ Moderator chose: <strong>{speaker}</strong></span>
            </div>
            """, unsafe_allow_html=True)

            if speaker == "END":
                st.success("🛑 Moderator ended the debate — consensus reached.")
                st.session_state.messages.append(
                    Message(sender="Moderator", content="🛑 Ended debate — consensus reached.", message_type="system")
                )
                break

            cfg = agent_config(speaker)
            if not cfg:
                continue
            st.session_state.currently_speaking = speaker

            with st.chat_message("assistant", avatar=cfg["icon"]):
                st.markdown(
                    f'<div class="msg-header">'
                    f'<span class="msg-name" style="color:{cfg["color"]};">{cfg["name"]}</span>'
                    f'<span class="msg-meta">· {cfg["provider"]} · {cfg["model_label"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                with st.spinner(f"{cfg['icon']} {cfg['name']} is thinking…"):
                    agents[speaker].act(st.session_state.goal, current_step=step, total_steps=max_steps)
                    msg = board.get_all()[-1]
                st.markdown(msg.content)

            st.session_state.messages.append(msg)
            st.session_state.steps_completed = step

        progress_bar.progress(1.0, text="✅ Debate complete")
        st.session_state.currently_speaking = None
        st.session_state.debate_done = True

        # ── Judge (8-dimension process rubric)
        with st.spinner("⚖️ Judge is evaluating the debate process..."):
            judge = Judge(
                model="groq:qwen/qwen3.8-27b",
                fallback_model="groq:openai/gpt-oss-120b",
            )
            scores = judge.evaluate(st.session_state.goal, board)
            st.session_state.judge_scores = scores

        # ── Save to DB
        if "error" not in scores:
            saved = save_debate_to_db(
                st.session_state.goal,
                board,
                scores,
                st.session_state.steps_completed,
            )
            if saved:
                st.toast("💾 Debate saved to eval database", icon="✅")

        st.balloons()

# ─────────────────────────────────────────────
# TAB 2: JUDGE — 8-dimension rubric
# ─────────────────────────────────────────────
with tab_judge:
    scores = st.session_state.get("judge_scores")
    if not scores:
        st.info("Run a debate first. The Judge evaluates it after the debate completes.")
    elif "error" in scores:
        st.error(f"Judge failed: {scores['error']}")
    else:
        st.markdown("### 📊 Process Evaluation")
        st.caption("The Judge scores the *debate process* — not which agent won.")

        # ── Rubric grid (4 columns × 2 rows)
        row1 = RUBRIC[:4]
        row2 = RUBRIC[4:]

        cols = st.columns(4)
        for i, (key, label, desc) in enumerate(row1):
            val = scores.get(key, 0)
            with cols[i]:
                st.metric(label, f"{val}/10")

        cols = st.columns(4)
        for i, (key, label, desc) in enumerate(row2):
            val = scores.get(key, 0)
            with cols[i]:
                st.metric(label, f"{val}/10")

        st.divider()

        # ── Overall score
        overall = scores.get("overall_score", 0)
        st.markdown(f"### 🏆 Overall: **{overall}/10**")
        st.progress(min(overall / 10, 1.0))

        # ── Verdict
        st.info(f"**Verdict:** {scores.get('verdict', 'N/A')}")

        st.divider()

        # ── Rubric legend
        with st.expander("📖 What each dimension means"):
            for key, label, desc in RUBRIC:
                st.markdown(f"**{label}** — {desc}")

# ─────────────────────────────────────────────
# TAB 3: EVALS
# ─────────────────────────────────────────────
with tab_evals:
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "eval_results.db"
    )

    col_r1, col_r2 = st.columns([4, 1])
    with col_r1:
        st.caption("Reads from `data/eval_results.db` — updated by the harness and by live debates.")
    with col_r2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    if not os.path.exists(db_path):
        st.info(
            "No eval runs yet. Run the harness locally:\n\n"
            "```bash\npython tests/eval_harness.py\n```\n\n"
            "Or run a debate in the **Debate** tab — it will be saved here automatically."
        )
    else:
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Get columns in DB to handle old vs new schema
            cur.execute("PRAGMA table_info(runs)")
            existing_cols = {row[1] for row in cur.fetchall()}

            # Latest run
            cur.execute(
                "SELECT run_group, MAX(timestamp) as latest FROM runs "
                "GROUP BY run_group ORDER BY latest DESC LIMIT 1"
            )
            row = cur.fetchone()

            if not row:
                st.info("Eval DB exists but has no runs yet.")
            else:
                latest_group = row["run_group"]
                cur.execute("SELECT * FROM runs WHERE run_group = ?", (latest_group,))
                rows = cur.fetchall()

                st.markdown(f"### 📊 Eval Run · `{latest_group}`")
                st.caption(f"{len(rows)} goals scored")

                # ── Aggregate across the 8 rubric dimensions
                def values_for(col):
                    if col not in existing_cols:
                        return []
                    return [r[col] for r in rows if r[col] is not None]

                def avg(arr):
                    return sum(arr) / len(arr) if arr else 0

                st.markdown("#### Aggregate Metrics")

                # Show the 8 rubric dimensions if available
                available_rubric = [(k, l, d) for k, l, d in RUBRIC if k in existing_cols]

                if available_rubric:
                    # Split into rows of 4
                    for chunk_start in range(0, len(available_rubric), 4):
                        chunk = available_rubric[chunk_start:chunk_start + 4]
                        cols = st.columns(4)
                        for i, (key, label, desc) in enumerate(chunk):
                            arr = values_for(key)
                            with cols[i]:
                                st.metric(label, f"{avg(arr):.2f}/10")
                else:
                    # Fallback for old schema
                    overall = values_for("overall_score")
                    reasoning = values_for("reasoning_quality")
                    c1, c2 = st.columns(2)
                    c1.metric("Overall", f"{avg(overall):.2f}/10")
                    c2.metric("Reasoning", f"{avg(reasoning):.2f}/10")

                st.divider()

                # ── Per-goal breakdown
                st.markdown("#### Per-Goal Breakdown")
                for r in rows:
                    overall_val = r["overall_score"] if "overall_score" in existing_cols else 0
                    overall_val = overall_val or 0

                    with st.expander(
                        f"`{r['goal_id']}` · overall **{overall_val:.1f}/10** · {r['difficulty']}"
                    ):
                        st.markdown(f"**Goal:** {r['goal']}")
                        st.markdown(
                            f"**Steps used:** {r['steps_used']} · "
                            f"**Category:** {r['category']} · "
                            f"**Timestamp:** {r['timestamp'][:19]}"
                        )
                        st.markdown(f"**Verdict:** {r['verdict']}")

                        # Show all available rubric dimensions for this row
                        if available_rubric:
                            st.markdown("**Rubric scores:**")
                            sub_cols = st.columns(4)
                            for i, (key, label, desc) in enumerate(available_rubric):
                                val = r[key] if key in existing_cols else None
                                with sub_cols[i % 4]:
                                    st.metric(
                                        label.split(" ", 1)[-1],
                                        f"{val or 0:.1f}",
                                    )

                st.divider()
                st.markdown("#### All Runs")
                cur.execute(
                    "SELECT run_group, COUNT(*) as n, "
                    "AVG(overall_score) as avg_overall, "
                    "MAX(timestamp) as latest "
                    "FROM runs GROUP BY run_group ORDER BY latest DESC"
                )
                all_runs = cur.fetchall()
                for run in all_runs:
                    n = run["n"]
                    ao = run["avg_overall"] or 0
                    is_latest = run["run_group"] == latest_group
                    marker = " ⬅ latest" if is_latest else ""
                    st.caption(
                        f"`{run['run_group']}` · {n} goals · "
                        f"overall **{ao:.2f}**{marker}"
                    )

            conn.close()

        except Exception as e:
            st.error(f"Could not read eval DB: {e}")

# ─────────────────────────────────────────────
# TAB 4: RAW TRANSCRIPT
# ─────────────────────────────────────────────
with tab_raw:
    if not st.session_state.messages:
        st.info("No debate yet.")
    else:
        raw = "\n\n".join(
            f"[{m.sender}] ({m.message_type}): {m.content}"
            for m in st.session_state.messages
        )
        st.code(raw, language=None)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 Download as Markdown",
            data=f"# HIVE Debate — {timestamp}\n\n**Goal:** {st.session_state.goal}\n\n{raw}",
            file_name=f"hive_debate_{timestamp}.md",
            mime="text/markdown",
            use_container_width=True,
        )