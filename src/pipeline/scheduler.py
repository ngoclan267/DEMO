import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from src.analysis.runner import run_analysis_cycle
from src.config import get_settings
from src.logging_config import VN_TZ, configure_logging
from src.notifications.digest import run_daily_digest
from src.pipeline.runner import run_cycle

logger = logging.getLogger(__name__)


def run_full_cycle() -> None:
    """Thu thập (Collector+Processing Agent) rồi phân tích (Classification->Verification->
    Consensus->Pain Point Agent) ngay trong cùng 1 lượt — nếu không có bước phân tích, post mới
    thu thập sẽ nằm mãi ở trạng thái chưa phân loại (không có Prediction) trên dashboard."""
    run_cycle()
    run_analysis_cycle()


def main() -> None:
    configure_logging()
    interval = get_settings().collection_interval_minutes

    # timezone=VN_TZ: server production (Render/Railway) mặc định hệ thống UTC — không set tường
    # minh thì cron hour=7 bên dưới chạy lúc 7h UTC (= 14h VN), không phải 7h sáng VN như tên biến
    # ngụ ý. Đặt ở đây thì mọi job (kể cả "next run at..." log của APScheduler) đều theo giờ VN.
    scheduler = BlockingScheduler(timezone=VN_TZ)
    scheduler.add_job(run_full_cycle, "interval", minutes=interval, next_run_time=datetime.now(VN_TZ))
    # Bản tin tổng hợp hàng ngày — chạy riêng, không phụ thuộc chu kỳ thu thập+phân tích ở trên.
    # next_run_time=now(): chạy ngay lúc khởi động để BẮT KỊP trường hợp container restart trước
    # khi kịp qua mốc 7:00 (dev hay restart scheduler, nên trước đây daily_digest gần như không bao
    # giờ chạy được — xem DIGEST_COOLDOWN_HOURS trong digest.py, chặn gửi trùng khi restart nhiều
    # lần trong cùng 1 ngày).
    scheduler.add_job(run_daily_digest, "cron", hour=7, minute=0, next_run_time=datetime.now(VN_TZ))

    logger.info("Scheduler khởi động (giờ VN) — chạy pipeline mỗi %d phút, bản tin hàng ngày lúc 7:00 sáng VN", interval)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler dừng lại")


if __name__ == "__main__":
    main()
