import logging
from datetime import datetime
from zoneinfo import ZoneInfo

# Server chạy production (Render/Railway) mặc định hệ thống là UTC — nếu không quy đổi tường minh,
# log/lịch chạy scheduler sẽ hiển thị giờ UTC dù đội ở Việt Nam, dễ đọc nhầm giờ thật (vd cron "7:00"
# tưởng là 7h sáng VN nhưng chạy lúc 14h VN vì UTC+0). Quy đổi tường minh ở đây để đúng bất kể
# server đặt timezone hệ thống là gì.
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class VietnamTimeFormatter(logging.Formatter):
    """Ghi đè formatTime() để %(asctime)s luôn ra giờ Việt Nam, thay vì phụ thuộc timezone hệ thống
    (logging.Formatter mặc định dùng time.localtime())."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=VN_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f",{int(record.msecs):03d}"


def configure_logging(level: int = logging.INFO) -> None:
    """Dùng thay cho logging.basicConfig() thô ở mọi entrypoint chạy độc lập (scheduler, CLI runner)
    — để log của cả 3 nơi hiển thị cùng 1 giờ Việt Nam, không lệch nhau."""
    handler = logging.StreamHandler()
    handler.setFormatter(VietnamTimeFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=level, handlers=[handler])
