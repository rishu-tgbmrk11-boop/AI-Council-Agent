# tools/python_repl.py
import io
import sys
import contextlib


def python_repl(code: str) -> str:
    """
    Execute Python code and return the output. Use this for calculations,
    data analysis, or to verify mathematical claims. Only prints output —
    do not use for file operations or network calls.
    """
    print(f"\n🔧 [TOOL] python_repl(code='{code[:60]}...')")

    # Safety: block dangerous imports
    forbidden = ["import os", "import sys", "import subprocess",
                 "open(", "__import__", "eval(", "exec("]
    for word in forbidden:
        if word in code:
            return f"Error: '{word}' is not allowed in the REPL."

    output = io.StringIO()
    local_vars = {}
    try:
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": __builtins__}, local_vars)
        result = output.getvalue().strip()

        # If nothing was printed but there's a last expression, show it
        if not result and local_vars:
            last_val = list(local_vars.values())[-1]
            result = repr(last_val)

        return result or "(no output)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)[:200]}"