# Social Listening Multi-Agent Platform

Nền tảng Social Listening đa tác tử giúp doanh nghiệp (ưu tiên ngành ngân hàng
trong bản MVP) phát hiện sớm phản hồi tiêu cực, kiểm chứng chéo giữa các AI
Agent trước khi cảnh báo, và tổng hợp phản hồi thành các **pain point** thay
vì hiển thị từng bài viết rời rạc.

Xem `docs/PRD.md` và `docs/architecture_diagram.md` để biết đầy đủ bối cảnh,
phạm vi và kiến trúc.

## Kiến trúc thư mục

```
├── src/                # Backend: FastAPI + LangGraph agents
│   ├── agents/          # graph.py, state.py, nodes/, tools/
│   ├── api/              # routes.py
│   ├── models/            # Pydantic schemas
│   ├── services/           # LLM service, mock data
│   ├── config.py
│   └── main.py
├── frontend/            # Web app (SPA tĩnh - xem frontend/index.html)
├── tests/               # pytest (test_agents/, test_api/)
├── scripts/             # AI logging hooks (Claude/Cursor/Codex/Gemini/Copilot)
├── .claude/ .codex/ .cursor/ .gemini/   # cấu hình hook theo từng công cụ
├── .agents/             # Antigravity rules + workflows
├── .ai-log/             # log sử dụng AI (tự sinh)
├── docs/                # PRD, brief, guidebook 10 chương, architecture diagram
├── eval/                # kết quả đánh giá (PRD mục 18)
├── presentation/        # dàn ý Demo Day
├── .github/workflows/   # CI (lint, test, docker build)
├── Dockerfile / docker-compose.yml
```

## Chạy nhanh (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn src.main:app --reload
# API: http://localhost:8000/docs
```

Mở `frontend/index.html` trực tiếp trên trình duyệt để xem giao diện demo
(dữ liệu mock, không cần backend chạy).

## Chạy bằng Docker

```bash
docker compose up --build
# API:      http://localhost:8000
# Frontend: http://localhost:3000
```

## Kiểm thử

```bash
pytest
```

## Ghi log sử dụng AI

```bash
bash scripts/setup_hooks.sh
python scripts/log_manual.py "ChatGPT" "Mô tả ngắn gọn việc đã dùng"
```

## Luồng agent (LangGraph)

```
Collector → Processing → Classification → Verification →
Consensus → Pain Point → Notification
```

Chi tiết: `src/agents/graph.py`, `docs/architecture_diagram.md`.
