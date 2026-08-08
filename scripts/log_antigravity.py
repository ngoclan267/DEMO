#!/usr/bin/env python3
"""
Antigravity IDE prompt scanner.
Quet thu muc .agents/ de tim cac prompt/workflow da chay trong Antigravity IDE
va ghi lai vao .ai-log/antigravity.jsonl.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".agents"
LOG_DIR = ROOT / ".ai-log"


def scan() -> list[dict]:
    events = []
    if not AGENTS_DIR.exists():
        return events
    for path in AGENTS_DIR.rglob("*.md"):
        events.append({
            "file": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        })
    return events


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    events = scan()
    with open(LOG_DIR / "antigravity.jsonl", "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"[log_antigravity] scanned {len(events)} file(s)")


if __name__ == "__main__":
    main()
