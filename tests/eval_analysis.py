# tests/eval_analysis.py
import sys
import os
import sqlite3
from collections import defaultdict

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "eval_results.db"
)


def analyze(run_group=None):
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # If no run_group provided, use the latest
    if run_group is None:
        cur.execute(
            "SELECT run_group, MAX(timestamp) FROM runs "
            "GROUP BY run_group ORDER BY MAX(timestamp) DESC LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            print("No runs found in the database.")
            return
        run_group = row[0]

    cur.execute("SELECT * FROM runs WHERE run_group = ?", (run_group,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"No results for run_group={run_group}")
        return

    print(f"\n{'='*70}")
    print(f"EVAL ANALYSIS — {run_group}")
    print(f"{'='*70}")
    print(f"Total goals: {len(rows)}\n")

    # ── Helper: safe average
    def avg(values):
        return sum(values) / len(values) if values else 0

    # ── Extract all dimension values
    def col(name):
        return [r[name] for r in rows if r[name] is not None]

    # ── Aggregate metrics (8 dimensions)
    print("── Aggregate Metrics ──")
    dimensions = [
        ("Overall Score",           "overall_score"),
        ("Reasoning Quality",       "reasoning_quality"),
        ("Evidence Grounding",      "evidence_grounding"),
        ("Perspective Integration", "perspective_integration"),
        ("Disagreement Resolution", "disagreement_resolution"),
        ("Hallucination Absence",   "hallucination_absence"),
        ("Process Engagement",      "process_engagement"),
        ("Convergence Quality",     "convergence_quality"),
    ]

    for label, key in dimensions:
        arr = col(key)
        if not arr:
            print(f"  {label:26} no data")
            continue
        a = avg(arr)
        lo = min(arr)
        hi = max(arr)
        bar = "█" * int(round(a))
        print(f"  {label:26} avg={a:5.2f}  min={lo:5.2f}  max={hi:5.2f}  {bar}")

    # ── Per-goal breakdown
    print(f"\n── Per-Goal Breakdown ──")
    header = (
        f"  {'Goal ID':<18} {'Category':<16} {'Diff':<7} "
        f"{'Overall':<8} {'Reason':<8} {'Evid':<6} {'Integ':<7} {'Steps':<6}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    for r in rows:
        def val(k):
            v = r[k] if k in r.keys() else None
            return f"{v:.1f}" if isinstance(v, (int, float)) else "-"

        print(
            f"  {r['goal_id']:<18} "
            f"{(r['category'] or ''):<16} "
            f"{(r['difficulty'] or ''):<7} "
            f"{val('overall_score'):<8} "
            f"{val('reasoning_quality'):<8} "
            f"{val('evidence_grounding'):<6} "
            f"{val('perspective_integration'):<7} "
            f"{r['steps_used']:<6}"
        )

    # ── Weakest & strongest dimensions across the run
    print(f"\n── Dimension Health ──")
    dim_avgs = {}
    for label, key in dimensions:
        arr = col(key)
        if arr:
            dim_avgs[label] = avg(arr)

    if dim_avgs:
        sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1])
        weakest = sorted_dims[0]
        strongest = sorted_dims[-1]
        print(f"  🔴 Weakest:    {weakest[0]} ({weakest[1]:.2f}/10)")
        print(f"  🟢 Strongest:  {strongest[0]} ({strongest[1]:.2f}/10)")

    # ── Best and worst debates
    if col("overall_score"):
        sorted_rows = sorted(rows, key=lambda r: r["overall_score"] or 0)

        print(f"\n── 🏆 Best Debate ──")
        best = sorted_rows[-1]
        print(f"  {best['goal_id']}: {best['overall_score']}/10")
        print(f"  Verdict: {best['verdict'][:200] if best['verdict'] else 'N/A'}")

        print(f"\n── 🔴 Worst Debate ──")
        worst = sorted_rows[0]
        print(f"  {worst['goal_id']}: {worst['overall_score']}/10")
        print(f"  Verdict: {worst['verdict'][:200] if worst['verdict'] else 'N/A'}")

    # ── Compare all runs (if multiple exist)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT run_group, COUNT(*) as n, "
        "AVG(overall_score) as avg_overall, "
        "AVG(perspective_integration) as avg_integration, "
        "AVG(evidence_grounding) as avg_evidence, "
        "MAX(timestamp) as latest "
        "FROM runs GROUP BY run_group ORDER BY latest DESC"
    )
    all_runs = cur.fetchall()
    conn.close()

    if len(all_runs) > 1:
        print(f"\n── All Runs (history) ──")
        for run in all_runs:
            marker = " ⬅ current" if run["run_group"] == run_group else ""
            print(
                f"  {run['run_group']} · {run['n']} goals · "
                f"overall {run['avg_overall'] or 0:.2f} · "
                f"integr {run['avg_integration'] or 0:.2f} · "
                f"evid {run['avg_evidence'] or 0:.2f}{marker}"
            )

    print()


if __name__ == "__main__":
    run_group = sys.argv[1] if len(sys.argv) > 1 else None
    analyze(run_group)