# ui/app.py
import streamlit as st
import sys
import os
import time
import json
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
    /* Global */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    /* Hero header */
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

    /* Agent badges */
    .agent-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
        letter-spacing: 0.3px;
    }

    /* Sidebar agent card */
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

    /* Status dot animations */
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.3); }
    }
    .status-speaking { animation: pulse 1.2s infinite; }

    /* Step divider */
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

    /* Message card */
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

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: #16213e;
        border: 1px solid #2d3561;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stMetricLabel"] { color: #8892b0 !important; }

    /* Tabs */
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
            "When someone quotes a number, verify it with python_repl."
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
        "model": "openrouter:nvidia/nemotron-3-super-120b-a12b:free",
        "persona": (
            "You are a creative lateral thinker. You bring current facts, statistics, and "
            "external context. When you need pricing or recent data, call web_search ONCE. "
            "If the first result gives you a partial answer, use what you have — do NOT "
            "search again. Then immediately write your argument."
        ),
        "fallback": "groq:openai/gpt-oss-120b",
        "tools": [web_search],
        "tool_names": ["web_search"],
        "icon": "🎯",
        "color": "#76B900",
        "provider": "OpenRouter",
        "model_label": "Nemotron 3 Super",
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
        "tools": [],
        "tool_names": [],
        "icon": "🐉",
        "color": "#FF6B35",
        "provider": "Groq",
        "model_label": "Qwen 3.8 27B",
    },
]

def agent_config(name: str):
    return next((a for a in COUNCIL if a["name"] == name), None)

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
        A council of three AI architectures — GPT-OSS, Nemotron, and Qwen — 
        debating under a dynamic moderator with independent evaluation.
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

    start = st.button("🚀 Start Debate", use_container_width=True, type="primary", disabled=st.session_state.debate_done and False)

    st.divider()
    st.markdown("### 🎭 The Council")

    for agent in COUNCIL:
        count = sum(1 for m in st.session_state.messages if m.sender == agent["name"])
        speaking = st.session_state.currently_speaking == agent["name"]

        # Status
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
tab_debate, tab_judge, tab_raw = st.tabs(["💬 Debate", "⚖️ Judge", "📄 Raw Transcript"])

# ─────────────────────────────────────────────
# TAB 1: DEBATE
# ─────────────────────────────────────────────
with tab_debate:
    if not st.session_state.messages and not start:
        st.info("👈 Set a goal in the sidebar and click **Start Debate** to begin.")

    # Render existing history
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

    # Run the debate
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

        # Post goal
        goal_msg = Message(sender="User", content=st.session_state.goal, role="user", message_type="goal")
        board.post(goal_msg)
        st.session_state.messages.append(goal_msg)
        with st.chat_message("user"):
            st.markdown(f"**🎯 Goal:** {st.session_state.goal}")

        # Progress bar
        progress_bar = st.progress(0.0, text="Starting debate...")

        # Moderator-driven debate
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

            # Step header
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

        # ── Run Judge after debate
        with st.spinner("⚖️ Judge is evaluating..."):
            judge = Judge(
                model="openrouter:nvidia/nemotron-3-super-120b-a12b:free",
                fallback_model="groq:qwen/qwen3.8-27b",
            )
            scores = judge.evaluate(st.session_state.goal, board)
            st.session_state.judge_scores = scores

        st.balloons()

# ─────────────────────────────────────────────
# TAB 2: JUDGE
# ─────────────────────────────────────────────
with tab_judge:
    scores = st.session_state.get("judge_scores")
    if not scores:
        st.info("Run a debate first. The Judge evaluates it after the debate completes.")
    elif "error" in scores:
        st.error(f"Judge failed: {scores['error']}")
    else:
        # ── Synthesis vs Individuals
        st.markdown("### 🥊 Individual vs. Synthesis")

        individual_scores = scores.get("individual_scores", {})
        synthesis_score = scores.get("synthesis_score", 0)
        best_individual = scores.get("best_individual", "N/A")
        best_score = scores.get("best_individual_score", 0)
        delta = scores.get("synthesis_delta", 0)

        cols = st.columns(len(individual_scores) + 1)
        for i, (name, score) in enumerate(individual_scores.items()):
            cfg = agent_config(name)
            if cfg:
                with cols[i]:
                    st.metric(
                        f"{cfg['icon']} {name}",
                        f"{score}/10",
                        delta="👑 best" if name == best_individual else f"{score - best_score:+.1f}",
                    )
        with cols[-1]:
            st.metric("🏆 Synthesis", f"{synthesis_score}/10", delta=f"{delta:+.1f} vs best")

        emoji = "🟢" if delta > 0 else ("🟡" if delta == 0 else "🔴")
        st.info(f"{emoji} **Synthesis verdict:** {scores.get('synthesis_verdict', 'N/A')}")

        st.divider()

        # ── Debate quality
        st.markdown("### 📊 Debate Quality")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🧠 Reasoning", f"{scores.get('reasoning_quality', 0)}/10")
        c2.metric("🎨 Diversity", f"{scores.get('perspective_diversity', 0)}/10")
        c3.metric("🔍 Depth", f"{scores.get('depth_of_debate', 0)}/10")
        c4.metric("🏆 Final Answer", f"{scores.get('final_answer_quality', 0)}/10")

        overall = scores.get("overall_score", 0)
        st.markdown(f"### Overall: **{overall}/10**")
        st.progress(min(overall / 10, 1.0))
        st.info(f"**Verdict:** {scores.get('verdict', 'N/A')}")

# ─────────────────────────────────────────────
# TAB 3: RAW TRANSCRIPT
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

        # Download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 Download as Markdown",
            data=f"# HIVE Debate — {timestamp}\n\n**Goal:** {st.session_state.goal}\n\n{raw}",
            file_name=f"hive_debate_{timestamp}.md",
            mime="text/markdown",
            use_container_width=True,
        )