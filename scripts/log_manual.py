#!/usr/bin/env python3
"""
Manual log cho cac cong cu khong ho tro hook tu dong (vi du ChatGPT web, cong cu web khac).
Chay: python scripts/log_manual.py "ChatGPT" "Mo ta ngan gon prompt/ket qua da su dung"
"""
import sys
from scripts.log_hook import log_event


def main() -> None:
    if len(sys.argv) < 3:
        print('Usage: log_manual.py "<tool_name>" "<mo ta>"')
        sys.exit(1)
    tool, description = sys.argv[1], sys.argv[2]
    log_event(tool.lower(), {"description": description, "source": "manual"})
    print(f"[log_manual] logged manual entry for {tool}")


if __name__ == "__main__":
    main()
