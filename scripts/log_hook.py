#!/usr/bin/env python3
"""
Auto-log hook cho Claude Code / Cursor / Codex / Gemini / Copilot.
Duoc goi boi cau hinh hook trong .claude/.codex/.cursor/.gemini tuong ung.
Ghi moi lan tuong tac AI vao .ai-log/<tool>.jsonl de phuc vu bao cao muc do
su dung AI trong qua trinh phat trien (theo yeu cau mon hoc / do an).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / ".ai-log"


def log_event(tool: str, event: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    entry = {"tool": tool, "timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with open(LOG_DIR / f"{tool}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: log_hook.py <tool_name> [event_json]")
        sys.exit(1)
    tool = sys.argv[1]
    event = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"note": "no payload provided"}
    log_event(tool, event)
    print(f"[log_hook] logged event for {tool}")


if __name__ == "__main__":
    main()
