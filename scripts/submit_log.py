#!/usr/bin/env python3
"""
Tong hop toan bo log trong .ai-log/ thanh mot bao cao tom tat (submit khi git push).
Duoc goi tu .github/workflows/ci.yml.
"""
import json
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / ".ai-log"


def main() -> None:
    if not LOG_DIR.exists():
        print("[submit_log] khong co thu muc .ai-log, bo qua")
        return

    summary: dict[str, int] = {}
    for log_file in LOG_DIR.glob("*.jsonl"):
        with open(log_file, encoding="utf-8") as f:
            summary[log_file.stem] = sum(1 for _ in f)

    report_path = LOG_DIR / "summary.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[submit_log] wrote summary to {report_path}: {summary}")


if __name__ == "__main__":
    main()
