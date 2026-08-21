"""Tách 3 khái niệm đang bị gộp vào một chữ "xác minh"

Trước đây `predictions.verification_status` KHÔNG mang nghĩa xác minh — nó chỉ trả lời "có tìm
được văn bản chính thức nào nói về chuyện này không". Hệ quả: 90% phản hồi hiển thị đồng thời
"Chưa xác minh" + "Xác nhận là vấn đề thật", đọc như mâu thuẫn.

Sau migration này:
  - reference_status      : đối chiếu văn bản chính thức (nghĩa CŨ, chỉ đổi tên cho đúng)
  - verification_status   : xác minh DANH TÍNH khách hàng qua CRM (nghĩa MỚI, dữ liệu bắt đầu lại)
  - content_reliability   : AI đánh giá độ tin cậy nội dung theo tính cụ thể của mô tả

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

reference_status_type = sa.Enum("matched", "no_match", "conflicting", name="reference_status_type")
identity_status_type = sa.Enum("verified", "unverified", name="identity_status_type")
content_reliability_type = sa.Enum("high", "medium", "low", name="content_reliability_type")
painpoint_reference_status = sa.Enum("matched", "no_match", "conflicting", name="painpoint_reference_status")


def upgrade():
    bind = op.get_bind()

    # --- predictions: đổi tên cột cũ TRƯỚC khi tạo cột mới cùng tên "verification_status" ---
    op.alter_column("predictions", "verification_status", new_column_name="reference_status")
    op.alter_column("predictions", "verification_confidence", new_column_name="reference_confidence")
    op.alter_column("predictions", "verified_at", new_column_name="reference_checked_at")

    # Đổi giá trị enum: verified->matched, unverified->no_match (conflicting giữ nguyên).
    # Postgres không cho đổi trực tiếp giá trị enum -> tạo type mới rồi cast qua text.
    reference_status_type.create(bind)
    op.execute(
        "ALTER TABLE predictions ALTER COLUMN reference_status TYPE reference_status_type "
        "USING CASE reference_status::text "
        "  WHEN 'verified' THEN 'matched' "
        "  WHEN 'unverified' THEN 'no_match' "
        "  ELSE 'conflicting' "
        "END::reference_status_type"
    )
    op.execute("DROP TYPE verification_status_type")

    # --- predictions: cột mới ---
    # verification_status dùng lại TÊN cũ nhưng NGHĨA mới (danh tính khách hàng). An toàn vì cột cũ
    # đã được đổi tên ở trên, không dòng nào mang giá trị cũ sang cột này. Mặc định 'unverified'
    # cho mọi dòng vì chưa có tích hợp CRM.
    identity_status_type.create(bind)
    op.add_column(
        "predictions",
        sa.Column("verification_status", identity_status_type, nullable=False, server_default="unverified"),
    )
    op.add_column("predictions", sa.Column("identity_checked_at", sa.DateTime(timezone=True), nullable=True))

    content_reliability_type.create(bind)
    op.add_column("predictions", sa.Column("content_reliability", content_reliability_type, nullable=True))

    # --- pain_points.status: cũng là kết quả gộp đối chiếu văn bản, đổi tên cho nhất quán ---
    op.alter_column("pain_points", "status", new_column_name="reference_status")
    painpoint_reference_status.create(bind)
    op.execute(
        "ALTER TABLE pain_points ALTER COLUMN reference_status DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE pain_points ALTER COLUMN reference_status TYPE painpoint_reference_status "
        "USING CASE reference_status::text "
        "  WHEN 'verified' THEN 'matched' "
        "  WHEN 'unverified' THEN 'no_match' "
        "  ELSE 'conflicting' "
        "END::painpoint_reference_status"
    )
    op.execute("ALTER TABLE pain_points ALTER COLUMN reference_status SET DEFAULT 'no_match'")
    op.execute("DROP TYPE painpoint_status")


def downgrade():
    bind = op.get_bind()

    old_painpoint_status = sa.Enum("unverified", "verified", "needs_review", name="painpoint_status")
    old_painpoint_status.create(bind)
    op.execute("ALTER TABLE pain_points ALTER COLUMN reference_status DROP DEFAULT")
    op.execute(
        "ALTER TABLE pain_points ALTER COLUMN reference_status TYPE painpoint_status "
        "USING CASE reference_status::text "
        "  WHEN 'matched' THEN 'verified' "
        "  WHEN 'no_match' THEN 'unverified' "
        "  ELSE 'needs_review' "
        "END::painpoint_status"
    )
    op.execute("ALTER TABLE pain_points ALTER COLUMN reference_status SET DEFAULT 'unverified'")
    op.execute("DROP TYPE painpoint_reference_status")
    op.alter_column("pain_points", "reference_status", new_column_name="status")

    op.drop_column("predictions", "content_reliability")
    content_reliability_type.drop(bind)
    op.drop_column("predictions", "identity_checked_at")
    op.drop_column("predictions", "verification_status")
    identity_status_type.drop(bind)

    old_verification_status = sa.Enum("verified", "unverified", "conflicting", name="verification_status_type")
    old_verification_status.create(bind)
    op.execute(
        "ALTER TABLE predictions ALTER COLUMN reference_status TYPE verification_status_type "
        "USING CASE reference_status::text "
        "  WHEN 'matched' THEN 'verified' "
        "  WHEN 'no_match' THEN 'unverified' "
        "  ELSE 'conflicting' "
        "END::verification_status_type"
    )
    op.execute("DROP TYPE reference_status_type")
    op.alter_column("predictions", "reference_checked_at", new_column_name="verified_at")
    op.alter_column("predictions", "reference_confidence", new_column_name="verification_confidence")
    op.alter_column("predictions", "reference_status", new_column_name="verification_status")
