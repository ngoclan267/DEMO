"""Nhận diện các Source trùng ĐỊNH DANH APP THẬT (package_name cho google_play, app_id cho
app_store) nhưng nằm ở các topic khác nhau — nhiều topic có thể (vô tình hoặc cố ý, vd 1 tài khoản
demo và 1 tài khoản thật cùng theo dõi TPBank Mobile) cùng crawl đúng 1 app. Trước khi có module
này, mỗi source tự crawl và tự đưa post vào hàng đợi LLM riêng dù nội dung trùng gần như tuyệt đối
giữa các topic — tốn gấp đôi/gấp ba quota Gemini free-tier một cách vô ích.

Quy ước: trong mỗi nhóm source trùng định danh, source có Source.created_at SỚM NHẤT là
'canonical' — chỉ nó mới thực sự gọi API bên ngoài và được đưa vào hàng đợi phân tích LLM. Các
source còn lại ('follower') đồng bộ content + Prediction lại từ canonical (xem
src/pipeline/runner.py::_sync_post_source_from_canonical) và bị loại khỏi hàng đợi phân tích (xem
src/analysis/runner.py::run_analysis_cycle) — không bao giờ tự gọi LLM cho review đã có kết quả ở
nơi khác.
"""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import Source

# Trường trong Source.config coi là định danh app THẬT của từng loại nguồn — chỉ 2 loại này có
# review công khai định danh rõ bằng 1 app cụ thể (package_name/app_id); bank_website định danh
# bằng domain (lỏng hơn, dễ khớp nhầm 2 topic KHÔNG cùng site) nên cố ý chưa đưa vào đây.
_IDENTITY_FIELD_BY_SOURCE_TYPE = {"google_play": "package_name", "app_store": "app_id"}


def source_identity(source_type: str, config: dict) -> str | None:
    """None nghĩa là không xác định được định danh (loại nguồn không hỗ trợ, hoặc config chưa được
    resolve — vd còn ở dạng {"query": "..."} chưa tự tìm ra package_name/app_id thật)."""
    field = _IDENTITY_FIELD_BY_SOURCE_TYPE.get(source_type)
    if field is None:
        return None
    value = config.get(field)
    return str(value) if value else None


def group_followers(
    sources: list[tuple[UUID, str, dict, datetime]],
) -> dict[UUID, UUID]:
    """Input: danh sách (source_id, source_type, config, created_at). Output: map follower_source_id
    -> canonical_source_id, chỉ chứa các source KHÔNG phải canonical trong nhóm của nó. Source đứng
    một mình (không trùng định danh với ai) không xuất hiện trong kết quả."""
    groups: dict[tuple[str, str], list[tuple[datetime, UUID]]] = defaultdict(list)
    for source_id, source_type, config, created_at in sources:
        identity = source_identity(source_type, config)
        if identity is None:
            continue
        groups[(source_type, identity)].append((created_at, source_id))

    followers: dict[UUID, UUID] = {}
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda pair: pair[0])
        canonical_id = group[0][1]
        for _, follower_id in group[1:]:
            followers[follower_id] = canonical_id
    return followers


def resolve_follower_sources(session: Session) -> dict[UUID, UUID]:
    rows = session.query(Source.id, Source.type, Source.config, Source.created_at).all()
    return group_followers(list(rows))
