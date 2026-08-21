"""notifications: thêm loại 'daily_digest' + cho phép pain_point_id NULL

Bản tin tổng hợp hàng ngày là thông báo Ở CẤP TOPIC (không gắn với 1 pain point cụ thể), khác 3
loại hiện có (threshold_alert/assigned/resolved đều gắn 1 pain_point_id cụ thể). Cần nới
pain_point_id thành nullable để lưu được loại này. Đơn giản hơn nhiều so với đợt đổi giá trị enum
0005 (0005 phải map lại toàn bộ giá trị cũ) — ở đây chỉ THÊM giá trị mới, không đổi giá trị cũ.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # Postgres 12+ cho phép ADD VALUE trong transaction, miễn không dùng giá trị đó trong CÙNG
    # transaction — ở đây chỉ thêm, không có DML nào dùng 'daily_digest' trong migration này.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'daily_digest'")
    op.alter_column("notifications", "pain_point_id", nullable=True)


def downgrade():
    # Không thể xoá 1 giá trị enum trực tiếp — tạo lại type như 0005 đã làm. Notification loại
    # 'daily_digest' (nếu có) được gộp về 'threshold_alert' vì downgrade vốn đã chấp nhận mất
    # thông tin phân loại (giống cách 0008.downgrade xoá thẳng cột notification_type).
    bind = op.get_bind()
    old_type = sa.Enum("threshold_alert", "assigned", "resolved", name="notification_type_old")
    old_type.create(bind)
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN notification_type TYPE notification_type_old "
        "USING CASE notification_type::text "
        "  WHEN 'daily_digest' THEN 'threshold_alert' "
        "  ELSE notification_type::text "
        "END::notification_type_old"
    )
    op.execute("DROP TYPE notification_type")
    op.execute("ALTER TYPE notification_type_old RENAME TO notification_type")

    # Digest cũ (pain_point_id NULL) phải bị xoá trước, nếu không NOT NULL sẽ vi phạm ràng buộc.
    op.execute("DELETE FROM notifications WHERE pain_point_id IS NULL")
    op.alter_column("notifications", "pain_point_id", nullable=False)
