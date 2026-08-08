#!/usr/bin/env bash
# One-time hook installer: lien ket cac hook cho Claude/Cursor/Codex/Gemini/Copilot
# vao scripts/log_hook.py de tu dong ghi log su dung AI trong qua trinh phat trien.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT_DIR/.ai-log"

echo "Cai dat AI logging hooks tai: $ROOT_DIR"

chmod +x "$ROOT_DIR/scripts/log_hook.py" \
         "$ROOT_DIR/scripts/log_antigravity.py" \
         "$ROOT_DIR/scripts/log_manual.py" \
         "$ROOT_DIR/scripts/submit_log.py"

echo "-> scripts/*.py da duoc cap quyen thuc thi"
echo "-> Cau hinh hook duoc doc tu .claude/ .codex/ .cursor/ .gemini/"
echo "-> Antigravity workflows duoc doc tu .agents/"
echo "Hoan tat. Chay 'python scripts/log_manual.py \"ChatGPT\" \"mo ta\"' de ghi log thu cong."
