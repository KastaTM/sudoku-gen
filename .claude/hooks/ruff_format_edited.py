"""Claude Code PostToolUse hook: format a Python file right after it is edited.

Reads the hook payload from stdin and never fails the tool call.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        file_path = str(payload["tool_input"]["file_path"])
    except (ValueError, KeyError, TypeError):
        return 0
    if not file_path.endswith(".py"):
        return 0
    if shutil.which("uv"):
        command = ["uv", "run", "--locked", "ruff", "format", file_path]
    elif shutil.which("ruff"):
        command = ["ruff", "format", file_path]
    else:
        return 0
    subprocess.run(command, check=False, capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
