from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.routes_admin import router as admin_router
from src.api.routes_auth import router as auth_router
from src.api.routes_billing import router as billing_router
from src.api.routes_contact import router as contact_router
from src.api.routes_dashboard import router as dashboard_router
from src.api.routes_notifications import router as notifications_router
from src.api.routes_topics import router as topics_router
from src.config import get_settings
from src.logging_config import configure_logging

# Phải gọi TRƯỚC khi bất kỳ module nào khác gọi logging.getLogger(...).info(...) — thiếu dòng này,
# mọi log INFO trong toàn bộ service (kể cả "Đã gửi email tới..." trong
# src/notifications/email.py) bị nuốt im lặng, chỉ log ERROR+ mới hiện (qua
# logging.lastResort mặc định của Python khi chưa cấu hình handler nào). scheduler.py đã tự gọi
# đúng ở entrypoint riêng của nó nên không bị ảnh hưởng — main.py (uvicorn) thì chưa, tới giờ mới
# phát hiện khi debug vụ email Brevo không thấy log xác nhận.
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    # Dev-only: CORS_ORIGINS là 1 danh sách cố định (mặc định chỉ cổng 3000), nhưng `next dev` tự
    # đổi sang cổng khác (3001, 3005...) bất cứ khi nào cổng mặc định đã bị chiếm — lúc đó mọi
    # request từ frontend bị CORS chặn âm thầm (trình duyệt chặn trước khi request thật được gửi,
    # nên backend không hề log lỗi gì, rất khó nhận ra nguyên nhân thật). Chỉ áp dụng ở development,
    # không nới lỏng CORS ở production.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.app_env == "development" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(topics_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(contact_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
